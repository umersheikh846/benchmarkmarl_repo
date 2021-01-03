import torch
import numpy as np
from torch.distributions import OneHotCategorical
from algorithms.r_matd3.algorithm.r_actor_critic import R_Actor, R_Critic
from algorithms.common.common_utils import get_state_dim, is_discrete, get_dim_from_space, DecayThenFlatSchedule, soft_update, hard_update, \
    gumbel_softmax, onehot_from_logits, make_onehot, gaussian_noise, avail_choose, MultiDiscrete


class R_MATD3Policy:
    def __init__(self, config, policy_config, train=True):

        self.config = config
        self.device = config['device']
        self.args = self.config["args"]        
        self.tau = self.args.tau
        self.lr = self.args.lr
        self.opti_eps = self.args.opti_eps
        self.weight_decay = self.args.weight_decay
        self.prev_act_inp = self.args.prev_act_inp

        self.central_obs_dim, self.central_act_dim = policy_config["cent_obs_dim"], policy_config["cent_act_dim"]
        self.obs_space = policy_config["obs_space"]
        self.obs_dim = get_dim_from_space(self.obs_space)
        self.act_space = policy_config["act_space"]
        self.act_dim = get_dim_from_space(self.act_space)
        self.hidden_size = self.args.hidden_size
        self.discrete_action = is_discrete(self.act_space)
        self.multidiscrete = isinstance(self.act_space, MultiDiscrete)

        self.actor = R_Actor(self.args, self.obs_dim, self.act_dim, self.discrete_action, self.device, take_prev_action=self.prev_act_inp)
        self.critic = R_Critic(self.args, self.central_obs_dim, self.central_act_dim, self.device)

        self.target_actor = R_Actor(self.args, self.obs_dim, self.act_dim, self.discrete_action, self.device, take_prev_action=self.prev_act_inp)
        self.target_critic = R_Critic(self.args, self.central_obs_dim, self.central_act_dim, self.device)
        # sync the target weights
        self.target_actor.load_state_dict(self.actor.state_dict())
        self.target_critic.load_state_dict(self.critic.state_dict())

        if train:
            self.actor_optimizer = torch.optim.Adam(self.actor.parameters(), lr=self.lr, eps=self.opti_eps, weight_decay=self.weight_decay)
            self.critic_optimizer = torch.optim.Adam(self.critic.parameters(), lr=self.lr, eps=self.opti_eps, weight_decay=self.weight_decay)

            if self.discrete_action:
                # eps greedy exploration
                self.exploration = DecayThenFlatSchedule(self.args.epsilon_start, self.args.epsilon_finish,
                                                         self.args.epsilon_anneal_time, decay="linear")
            else:
                # Set to none; gaussian noise will be added in get_actions
                self.exploration = None

    def get_actions(self, obs, prev_actions, actor_rnn_states, available_actions=None, use_target=False, t_env=None,
                    use_gumbel=False, explore=False):

        assert prev_actions is None or len(obs.shape) == len(prev_actions.shape)
        # obs is either an array of shape (batch_size, obs_dim) or (seq_len, batch_size, obs_dim)
        if len(obs.shape) == 2:
            batch_size = obs.shape[0]
            no_sequence = True
        else:
            batch_size = obs.shape[1]
            no_sequence = False

        eps = None
        if use_target:
            actor_out, new_rnn_states = self.target_actor(obs, prev_actions, actor_rnn_states)
        else:
            actor_out, new_rnn_states = self.actor(obs, prev_actions, actor_rnn_states)

        if self.discrete_action:
            if self.multidiscrete:
                if use_gumbel or explore or use_target:
                    onehot_actions = list(map(lambda a: gumbel_softmax(a, hard=True), actor_out))
                else:
                    onehot_actions = list(map(onehot_from_logits, actor_out))

                onehot_actions = torch.cat(onehot_actions, dim=-1)
                if explore:
                    # eps greedy exploration
                    batch_size = obs.shape[0]
                    eps = self.exploration.eval(t_env)
                    rand_numbers = torch.rand((batch_size, 1))
                    take_random = (rand_numbers < eps).int().view(-1, 1)

                    # random actions sample uniformly from action space
                    random_actions = [OneHotCategorical(logits=torch.ones(batch_size, self.act_dim[i])).sample() for i
                                      in range(len(self.act_dim))]
                    random_actions = torch.cat(random_actions, dim=1)
                    actions = (1 - take_random) * onehot_actions + take_random * random_actions
                else:
                    actions = onehot_actions
            else:
                if use_gumbel or explore or use_target:
                    onehot_actions = gumbel_softmax(actor_out, available_actions,
                                                    hard=True)  # gumbel has a gradient
                else:
                    onehot_actions = onehot_from_logits(actor_out, available_actions)  # no gradient

                if explore:
                    assert no_sequence, "Doesn't make sense to do exploration on a sequence!"
                    # eps greedy exploration
                    eps = self.exploration.eval(t_env)
                    rand_numbers = np.random.rand(batch_size, 1)
                    # random actions sample uniformly from action space
                    logits = torch.ones(batch_size, self.act_dim)
                    random_actions = avail_choose(logits, available_actions).sample()
                    random_actions = make_onehot(random_actions, batch_size, self.act_dim)
                    take_random = (rand_numbers < eps).astype(float)
                    actions = (1.0 - take_random) * onehot_actions.detach().cpu().numpy() + take_random * random_actions.cpu().numpy()
                else:
                    actions = onehot_actions
        else:
            if explore:
                assert no_sequence, "Cannot do exploration on a sequence!"
                actions = gaussian_noise(actor_out.shape, self.args.act_noise_std) + actor_out
            elif use_target:
                target_noise = gaussian_noise(actor_out.shape, self.args.target_noise_std).clamp(
                    -self.args.target_noise_clip, self.args.target_noise_clip)
                actions = actor_out + target_noise
            else:
                actions = actor_out
            # # clip the actions at the bounds of the action space
            # actions = torch.max(torch.min(actions, torch.from_numpy(self.act_space.high)), torch.from_numpy(self.act_space.low))

        return actions, new_rnn_states, eps

    def step_critic(self, cent_obs_list, cent_act_list, critic_rnn_state, use_target=False):
        cent_obs = torch.cat(cent_obs_list, dim=1).float()
        cent_act = torch.cat(cent_act_list, dim=1).float()
        if use_target:
            q1_values, q2_values, new_rnn_states = self.target_critic(cent_obs, cent_act, critic_rnn_state)
        else:
            q1_values, q2_values, new_rnn_states = self.critic(cent_obs, cent_act, critic_rnn_state)

        return q1_values, q2_values, new_rnn_states

    def init_hidden(self, num_agents, batch_size, use_numpy=False):
        if use_numpy:
            if num_agents == -1:
                return np.zeros((batch_size, self.hidden_size))
            else:
                return np.zeros((num_agents, batch_size, self.hidden_size))
        else:
            if num_agents == -1:
                return torch.zeros(batch_size, self.hidden_size)
            else:
                return torch.zeros(num_agents, batch_size, self.hidden_size)


    def get_random_actions(self, obs, available_actions=None):
        batch_size = obs.shape[0]
        if available_actions is not None:
            logits = torch.ones(batch_size, self.act_dim)
            random_actions = avail_choose(logits, available_actions)
            random_actions = random_actions.sample()
            random_actions = make_onehot(random_actions, batch_size, self.act_dim).cpu().numpy()
        else:
            if self.discrete_action:
                if self.multidiscrete:
                    random_actions = [OneHotCategorical(logits=torch.ones(batch_size, self.act_dim[i])).sample().numpy()
                                      for i in
                                      range(len(self.act_dim))]
                    random_actions = np.concatenate(random_actions, axis=-1)
                else:
                    random_actions = OneHotCategorical(logits=torch.ones(batch_size, self.act_dim)).sample().numpy()
            else:
                random_actions = np.random.uniform(self.act_space.low, self.act_space.high,
                                                   size=(batch_size, self.act_dim))

        return random_actions

    def soft_target_updates(self):
        # polyak updates to target networks
        soft_update(self.target_critic, self.critic, self.tau)
        soft_update(self.target_actor, self.actor, self.tau)

    def hard_target_updates(self):
        # polyak updates to target networks
        hard_update(self.target_critic, self.critic)
        hard_update(self.target_actor, self.actor)
