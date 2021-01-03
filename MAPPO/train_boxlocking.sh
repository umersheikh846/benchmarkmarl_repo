#!/bin/sh
env="BoxLocking"
scenario_name="quadrant"
task_type="all" # "all" "order" "order-return" "all-return"
num_agents=2
num_boxes=4
algo="boxlocking/mappo-gru"
seed_max=3

echo "env is ${env}, scenario is ${scenario_name}, num_agents is ${num_agents}, algo is ${algo}, seed is ${seed_max}"

for seed in `seq ${seed_max}`;
do
    echo "seed is ${seed}:"
    CUDA_VISIBLE_DEVICES=4 python train_hns_transfertask.py --env_name ${env} --algorithm_name ${algo} --scenario_name ${scenario_name} --task_type ${task_type} --num_agents ${num_agents} --num_boxes ${num_boxes} --seed ${seed} --n_rollout_threads 250 --num_mini_batch 1 --episode_length 240 --num_env_steps 100000000 --ppo_epoch 15 --gain 1
    echo "training is done!"
done
