SEED=42
ENV="ALE/SpaceInvaders-v5"
TRAIN_MODES="--first-mode 0 --last-mode 7"
STEPS=1400000
python run_experiments.py --env $ENV  --method_type Finetune  --total_timesteps $STEPS $TRAIN_MODES --seed $SEED
python run_experiments.py   --env $ENV  \
                            --method_type FuseNet   \
                            $TRAIN_MODES \
                            --seed $SEED \
                            --total_timesteps $STEPS \
                            --alpha_learning_rate 2.5e-3 \
                            --delta_theta_mode TAT \
                            --fuse_actor \
                            --tag "FuseActorOnlyRandn2.5e-3" \
# python run_experiments.py --env $ENV  --method_type Baseline  $TRAIN_MODES --seed $SEED --debug
# python run_experiments.py --env $ENV  --method_type CompoNet  $TRAIN_MODES --seed $SEED --debug
                            # --debug
# python run_experiments.py --env $ENV  --method_type PackNet   $TRAIN_MODES --seed $SEED
# python run_experiments.py --env $ENV  --method_type ProgNet   $TRAIN_MODES --seed $SEED
