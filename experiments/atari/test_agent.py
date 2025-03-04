import gymnasium as gym
import numpy as np
import torch
import argparse
import os
from stable_baselines3.common.atari_wrappers import (  # isort:skip
    ClipRewardEnv,
    EpisodicLifeEnv,
    FireResetEnv,
    MaxAndSkipEnv,
    NoopResetEnv,
)

from models import (
    CnnSimpleAgent,
    # DinoSimpleAgent,
    CnnCompoNetAgent,
    CnnTvNetAgent, 
    ProgressiveNetAgent,
    PackNetAgent,
    FuseNetAgent,
    CnnMaskAgent,
    FuseNetwMergeAgent,
    RewireAgent,
    CnnCbpAgent,
    CReLUsAgent,
)
from task_utils import parse_name_info, path_from_other_mode


def parse_arguments():
    parser = argparse.ArgumentParser()

    # fmt: off
    parser.add_argument("--load", type=str, required=True)

    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", type=int, default=None)

    parser.add_argument("--train_mode", type=int)
    parser.add_argument("--max-timesteps", type=int, default=1000)
    parser.add_argument("--num-episodes", type=int, default=10)
    parser.add_argument('--render', default=False, action='store_true')
    parser.add_argument('--csv', default=None, type=str)
    # fmt: on

    return parser.parse_args()


def make_env(env_id, idx, run_name, render_mode=None, mode=None):
    def thunk():
        env = gym.make(env_id, mode=mode, render_mode=render_mode)

        env = gym.wrappers.RecordEpisodeStatistics(env)

        # env = NoopResetEnv(env, noop_max=30)
        env = MaxAndSkipEnv(env, skip=4)
        # env = EpisodicLifeEnv(env)

        env = gym.wrappers.ResizeObservation(env, (84, 84))
        env = gym.wrappers.GrayScaleObservation(env)
        env = gym.wrappers.FrameStack(env, 4)
        return env

    return thunk

def convert_algorithm(algorithm):
    if algorithm not in ["Baseline", "Finetune"]:
        return algorithm
    conversion_dict = {
        "Baseline": "F1",
        "Finetune": "FN",
    }
    return conversion_dict.get(algorithm, "unknown")

def get_num_task(env):
    if "SpaceInvaders" in env:
        return 10
    elif "Freeway" in env:
        return 8

if __name__ == "__main__":
    args = parse_arguments()
    # env_name, train_mode, algorithm, seed = parse_name_info(args.load.split("/")[-1])
    env_name, train_mode, algorithm, seed = parse_name_info(args.load.split("/")[-1])
    mode = train_mode if args.mode is None else args.mode
    seed = args.seed
    print(
        f"\nEnvironment: {env_name}, train/test mode: {train_mode}/{mode}, algorithm: {algorithm}, seed: {seed}\n"
    )

    # make the environment
    envs = gym.vector.SyncVectorEnv([make_env(env_name, 1, run_name="test", mode=mode)])
    env_fn = make_env(
        env_name,
        0,
        run_name="test",
        mode=mode,
        render_mode="human" if args.render else None,
    )
    env = env_fn()

    # load the model
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if algorithm in ["F1", "FN", "Baseline", "Finetune"]:
        agent = CnnSimpleAgent.load(
            args.load, envs, load_critic=False, map_location=device
        )
    elif algorithm == "CompoNet":
        prevs_paths = [path_from_other_mode(args.load, i) for i in range(args.train_mode)]
        agent = CnnCompoNetAgent.load(
            args.load, envs, prevs_paths=prevs_paths, map_location=device
        )
    elif algorithm == "ProgNet":
        prevs_paths = [path_from_other_mode(args.load, i) for i in range(args.train_mode)]
        agent = ProgressiveNetAgent.load(
            args.load, envs, prevs_paths=prevs_paths, map_location=device
        )
    elif algorithm == "PackNet":
        task_id = None if args.mode == None else args.mode + 1
        agent = PackNetAgent.load(args.load, task_id=task_id, map_location=device)
        agent.network.set_view(task_id)

        if mode != train_mode:
            # load the actor and critic heads from the model trained in the testing task (game mode)
            path = path_from_other_mode(args.load, mode)
            ac = PackNetAgent.load(path, map_location=device)
            agent.critic = ac.critic
            agent.actor = ac.actor
    elif algorithm == "FuseNet":
        agent = FuseNetAgent.load(args.load, envs, map_location=device)
    elif algorithm == "FuseNetwMerge":
        agent = FuseNetwMergeAgent.load(args.load, envs, map_location=device)
    elif algorithm == "MaskNet":
        agent = CnnMaskAgent.load(args.load, envs, num_tasks=get_num_task(env_name), map_location=device)
    elif algorithm == "Rewire":
        agent = RewireAgent.load(args.load, envs, map_location=device)
        agent.set_task(args.mode)
    elif algorithm == "CReLUs":
        agent = CReLUsAgent.load(args.load, envs, map_location=device)
    elif algorithm == "CbpNet":
        agent = CnnCbpAgent.load(args.load, envs, map_location=device)
    else:
        print(f"Loading of agent type `{algorithm}` is not implemented.")
        quit(1)

    agent.to(device)

    #
    # Main loop
    # ~~~~~~~~~
    ep_rets = []
    for _ in range(args.num_episodes):
        observation, info = env.reset(seed=seed)

        ep_ret = 0
        for _ in range(args.max_timesteps):
            observation = torch.from_numpy(np.array(observation)).to(device) / 255.0
            observation = observation.unsqueeze(0)
            action, _, _, _ = agent.get_action_and_value(observation)

            observation, reward, terminated, truncated, info = env.step(
                action[0].item()
            )

            ep_ret += reward

            if terminated or truncated:
                print(f"Episodic return: {ep_ret}")
                ep_rets.append(ep_ret)
                break

    print()
    print("Avg. episodic return:", np.mean(ep_rets))

    if args.csv:
        exists = os.path.exists(args.csv)
        with open(args.csv, "w" if not exists else "a") as f:
            if not exists:
                f.write("algorithm,environment,train mode,test mode,seed,ep ret\n")
            for v in ep_rets:
                f.write(f"{convert_algorithm(algorithm)},{env_name},{train_mode},{mode},{seed},{v}\n")
