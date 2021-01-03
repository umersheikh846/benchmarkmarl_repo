# OFF-POLICY (Multi-agent version for StarCraftII/Hanabi/MPE/Hide-and-Seek)

## 1.Install

test on CUDA == 10.1

```Bash
# create conda environment
conda create -n mappo python==3.6.2
conda activate mappo
pip install torch==1.5.1+cu101 torchvision==0.6.1+cu101 -f https://download.pytorch.org/whl/torch_stable.html
pip install -r requirements.txt

# install off-policy package
cd OFF-POLICY
pip install -e .
```

- run.py in each algorithm subfold contains all hyper-parameters.
- default: use GPU, recurrent policy and shared policy

## 2. StarCraftII

### 2.1 Install StarCraftII [4.10](http://blzdistsc2-a.akamaihd.net/Linux/SC2.4.10.zip)

   ```Bash
unzip SC2.4.10.zip
# password is iagreetotheeula
echo "export SC2PATH=~/StarCraftII/" > ~/.bashrc
   ```

- download SMAC Maps, and move it to `~/StarCraftII/Maps/`.

- If you want stable id, you can copy the `stableid.json` from https://github.com/Blizzard/s2client-proto.git to `~/StarCraftII/`.

### 2.2 Train StarCraftII

The training scripts of StarCraftII can be found in `runner_scripts/`. 

- MADDPG: `run_sc_rmaddpg.sh`

- MASAC: `run_sc_rmasac.sh`

- MATD3: `run_sc_rmatd3.sh`

- QMIX: use QMIX-SC.
## 3. Hanabi

### 3.1 Hanabi

The environment code is reproduced from the hanabi open-source environment, but did some minor changes to fit the algorithms. Hanabi is a game for **2-5** players, best described as a type of cooperative solitaire.

### 3.2 Install Hanabi 

```Bash
pip install cffi
cd envs/hanabi
mkdir build & cd build
cmake ..
make -j
```

### 3.3 Train Hanabi

The training scripts of Hanabi-Small can be found in `runner_scripts/`. 

- MADDPG: `run_hanabi_rmaddpg.sh`

- MASAC: `run_hanabi_rmasac.sh`

- MATD3: `run_hanabi_rmatd3.sh`

- QMIX: `run_hanabi_qmix.sh`

## 4. MPE

### 4.1 Install MPE

```Bash
# install this package first
pip install seabon
```

3 Cooperative scenarios in MPE:

- simple_spread
- simple_speaker_listener
- simple_reference

### 4.2 Train MPE

The training scripts of MPE can be found in `runner_scripts/`. 

- MADDPG: `run_mpe_rmaddpg.sh`

- MASAC: `run_mpe_rmasac.sh`

- MATD3: `run_mpe_rmatd3.sh`

- QMIX: `run_mpe_qmix.sh`

## 5.Hide-and-Seek

we support multi-agent box locking and blueprint construction tasks in the hide-and-seek domain.

### 5.1 Install Hide-and-Seek

#### 5.1.1 Install MuJoCo

1. Obtain a 30-day free trial on the [MuJoCo website](https://www.roboti.us/license.html) or free license if you are a student. 

2. Download the MuJoCo version 2.0 binaries for [Linux](https://www.roboti.us/download/mujoco200_linux.zip).

3. Unzip the downloaded `mujoco200_linux.zip` directory into `~/.mujoco/mujoco200`, and place your license key at `~/.mujoco/mjkey.txt`.

4. Add this to your `.bashrc` and source your `.bashrc`.

   ```
   export LD_LIBRARY_PATH=~/.mujoco/mujoco200/bin${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
   export MUJOCO_KEY_PATH=~/.mujoco${MUJOCO_KEY_PATH}
   ```

#### 5.1.2 Intsall mujoco-py and mujoco-worldgen

1. You can install mujoco-py by running `pip install mujoco-py==2.0.2.13`. If you encounter some bugs, refer this official [repo](https://github.com/openai/mujoco-py) for help.

2. To install mujoco-worldgen, follow these steps:

   ```Bash
    # install mujuco_worldgen
    cd envs/hns/mujoco-worldgen/
    pip install -e .
    pip install xmltodict
    # if encounter enum error, excute uninstall
    pip uninstall enum34
   ```

### 5.2 Train Tasks

The training scripts of Hide-and-Seek can be found in `runner_scripts/`. 

boxlocking task:

- MADDPG: `run_boxlocking_rmaddpg.sh`
- RASAC: `run_boxlocking_rmasac.sh`
- MATD3: `run_boxlocking_rmatd3.sh`
- QMIX: `run_boxlocking_qmix.sh`

blueprint contruction task:

- MADDPG:`run_bpc_rmaddpg.sh`
- MASAC:`run_bpc_rmasac.sh`
- MATD3:`run_bpc_rmatd3.sh`
- QMIX:`run_bpc_qmix.sh`