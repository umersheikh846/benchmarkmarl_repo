from algorithms.r_matd3.run import parse_args
import sys
import os
from algorithms.common.common_utils import get_state_dim, get_dim_from_space
from envs.hanabi.rl_env import HanabiEnv
from algorithms.r_matd3.R_MATD3Trainable import RMATD3Trainable
import json
import torch
import numpy as np
import argparse
import time
from pathlib import Path

def main(args):
    # ray.init(local_mode=True)
    env_parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    env_parser.add_argument('--hanabi_name', type=str, default='Hanabi-Very-Small', help="Which env to run on")
    env_parser.add_argument('--num_players', type=int, default=2, help="number of players")
    env_parser.add_argument('--take_turn', action='store_false', default=True, help="take turn to take action")
    env_parser.add_argument('--use_cent_agent_obs', action='store_false', default=True, help="different central obs")
    env_parser.add_argument('--use_available_actions', action='store_false', default=True, help="take turn to take action")
    
    env_args = env_parser.parse_known_args(args)[0]

    # algorithm specific parameters
    alg_flags, alg_arg_dict = parse_args(args)

    # set seeds and # threads
    torch.manual_seed(alg_flags.seed)
    torch.cuda.manual_seed_all(alg_flags.seed)
    np.random.seed(alg_flags.seed)
    
    # cuda
    if alg_flags.cuda and torch.cuda.is_available():
        device = torch.device("cuda:0")
        torch.set_num_threads(1)
        if alg_flags.cuda_deterministic:
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
    else:
        device = torch.device("cpu")
        torch.set_num_threads(alg_flags.n_training_threads)

    # env for testing and warmup (contains parallel envs)
    env = HanabiEnv(env_args.hanabi_name, env_args.num_players, alg_flags.seed)
    #test_env = HanabiEnv(env_args.hanabi_name, env_args.num_players, alg_flags.seed)
    alg_arg_dict["n_agents"] = env.num_agents

    # setup file to output tensorboard, hyperparameters, and saved models
    model_dir = Path('../results') / alg_flags.env_name / env_args.hanabi_name / alg_flags.algorithm_name
    if not model_dir.exists():
        curr_run = 'run1'
    else:
        exst_run_nums = [int(str(folder.name).split('run')[1]) for folder in model_dir.iterdir() if str(folder.name).startswith('run')]
        if len(exst_run_nums) == 0:
            curr_run = 'run1'
        else:
            curr_run = 'run%i' % (max(exst_run_nums) + 1)

    run_dir = model_dir / curr_run
    if not run_dir.exists():
        os.makedirs(str(run_dir))
    with open(str(run_dir) + '/params.json', 'w+') as fp:
        json.dump(alg_arg_dict, fp)

    _, cent_act_dim, _ = get_state_dim(env.observation_space, env.action_space)
    cent_obs_dim = get_dim_from_space(env.share_observation_space[0])
    
    # create policies and mapping fn
    if alg_flags.share_policy:
        policy_info = {
            'policy_0': {"cent_obs_dim": cent_obs_dim,
                        "cent_act_dim": cent_act_dim,
                        "obs_space": env.observation_space[0],
                        "act_space": env.action_space[0]}
        }
        policy_mapping_fn = lambda id: 'policy_0'
    else:
        policy_info = {
            'policy_' + str(id): {"cent_obs_dim": cent_obs_dim,
                                "cent_act_dim": cent_act_dim,
                                "obs_space": env.observation_space[id],
                                "act_space": env.action_space[id]}
            for id in env.agent_ids
        }
        policy_mapping_fn = lambda id: 'policy_' + str(id)

    config = {"args": alg_flags, 
              "run_dir": run_dir, 
              "policy_info": policy_info, 
              "policy_mapping_fn": policy_mapping_fn,
              "env": env, 
              "test_env": env, 
              "agent_ids": env.agent_ids, 
              "take_turn":env_args.take_turn, 
              "use_cent_agent_obs":env_args.use_cent_agent_obs, 
              "use_available_actions":env_args.use_available_actions,
              "device": device}

    # trainable = MADDPGTrainable(config=config)
    trainable = RMATD3Trainable(config=config)
    test_times = (alg_flags.num_env_steps // alg_flags.test_interval) + 1
    for test_time in range(test_times):
        print("\n Hanabi {} Algo {} updates {}/{} times, total num timesteps {}/{}.\n"
                .format(env_args.hanabi_name,
                        alg_flags.algorithm_name,
                        test_time, 
                        test_times,
                        trainable.total_env_steps,
                        alg_flags.num_env_steps))
        trainable.train()
    trainable.logger.export_scalars_to_json(str(trainable.log_dir + '/summary.json'))
    trainable.logger.close()

if __name__ == "__main__":
    main(sys.argv[1:])
