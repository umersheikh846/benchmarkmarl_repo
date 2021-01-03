import torch
import numpy as np
from torch.distributions import OneHotCategorical
from algorithms.r_masac.algorithm.r_actor_critic import R_DiscreteActor, R_GaussianActor, R_Critic
from algorithms.common.common_utils import get_dim_from_space, soft_update, hard_update, onehot_from_logits, make_onehot, avail_choose, MultiDiscrete


class R_MASACPolicy:
    def __init__(self, config, policy_config, discrete, train=True):

        self.config = config
        self.device = config['device']
        self.args = self.config["args"]        
        self.tau = self.args.tau
        self.lr = self.args.lr
        self.target_entropy_coef = self.args.target_entropy_coef
        self.opti_eps = self.args.opti_eps
        self.weight_decay = self.args.weight_decay
        self.prev_act_inp = self.args.prev_act_inp

        self.central_obs_dim, self.central_act_dim = policy_config["cent_obs_dim"], policy_config["cent_act_dim"]
        self.obs_space = policy_config["obs_space"]
        self.obs_dim = get_dim_from_space(self.obs_space)
        self.act_space = policy_config["act_space"]
        self.act_dim = get_dim_from_space(self.act_space)
        self.hidden_size = self.args.hidden_size
        self.discrete_action = discrete
        self.multidiscrete = isinstance(self.act_space, MultiDiscrete)

        if self.discrete_action:
            self.actor = R_DiscreteActor(self.args, self.obs_dim, self.act_dim, self.device, take_prev_action=self.prev_act_inp)
            self.target_entropy = -np.log((1.0 / self.act_dim)) * self.target_entropy_coef # slightly less than max possible entropy

        else:
            self.actor = R_GaussianActor(self.args, self.obs_dim, self.act_dim, self.act_space, self.device, take_prev_action=self.prev_act_inp)
            self.target_entropy = -torch.prod(torch.Tensor(self.act_space.shape)).item()  # max possible entropy

        self.critic = R_Critic(self.args, self.central_obs_dim, self.central_act_dim, self.device, discrete=False)
        self.target_critic = R_Critic(self.args, self.central_obs_dim, self.central_act_dim, self.device, discrete=False)
        # sync the target weights
        self.target_critic.load_state_dict(self.critic.state_dict())

        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(), lr=self.lr, eps=self.opti_eps, weight_decay=self.weight_decay)
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(), lr=self.lr, eps=self.opti_eps, weight_decay=self.weight_decay)

        self.alpha = self.config["args"].alpha # will get updated via log_alpha
        self.log_alpha = torch.tensor(np.log(self.alpha), requires_grad=True)
        self.alpha_optimizer = torch.optim.Adam([self.log_alpha], lr=self.lr, eps=self.opti_eps, weight_decay=self.weight_decay)

    def get_actions(self, obs, prev_actions, actor_rnn_states, available_actions=None, sample=True, sample_gumbel=False):

        assert prev_actions is None or len(obs.shape) == len(prev_actions.shape)

        if sample:
            if self.discrete_action:
                # actions are the sample output
                actions, log_probs, _, rnn_outs = self.actor.sample(obs, prev_actions, actor_rnn_states, available_actions, sample_gumbel=sample_gumbel)

            else:
                # actions are the sample output
                actions, log_probs, _, rnn_outs = self.actor.sample(obs, prev_actions, actor_rnn_states, available_actions)
        else:
            # actions are the mode of the distribution
            _, log_probs, actions, rnn_outs = self.actor.sample(obs, prev_actions, actor_rnn_states, available_actions)

        return actions, log_probs, rnn_outs

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
        if self.discrete_action:
            return self.get_random_actions_discrete(obs, available_actions)
        else:
            return self.get_random_actions_continuous(obs)

    def get_random_actions_continuous(self, obs):
        assert len(obs.shape) == 2, "Cannot do random actions on sequence!"
        batch_size = obs.shape[0]

        random_actions = torch.from_numpy(np.random.uniform(self.act_space.low, self.act_space.high, size=(batch_size, self.act_dim)))
        return random_actions

    def get_random_actions_discrete(self, obs, available_actions=None):
        assert len(obs.shape) == 2, "No random actions on sequence"
        batch_size = obs.shape[0]
        if available_actions is not None:
            logits = torch.ones(batch_size, self.act_dim)
            random_actions = avail_choose(logits, available_actions)
            random_actions = random_actions.sample()
            random_actions = make_onehot(random_actions, batch_size, self.act_dim).cpu().numpy()
        else:
            if self.multidiscrete:
                random_actions = [OneHotCategorical(logits=torch.ones(batch_size, self.act_dim[i])).sample().numpy() for
                                  i in
                                  range(len(self.act_dim))]
                random_actions = np.concatenate(random_actions, axis=-1)
            else:
                random_actions = OneHotCategorical(logits=torch.ones(batch_size, self.act_dim)).sample().numpy()

        return random_actions

    def soft_target_updates(self):
        # polyak updates to target networks
        soft_update(self.target_critic, self.critic, self.tau)

    def hard_target_updates(self):
        # polyak updates to target networks
        hard_update(self.target_critic, self.critic)