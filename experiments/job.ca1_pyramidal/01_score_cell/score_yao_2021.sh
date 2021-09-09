#!/bin/bash
#SBATCH -n 4                # Number of cores (-n)
#SBATCH -N 1                # Ensure that all cores are on one Node (-N)
#SBATCH -t 0-03:00          # Runtime in D-HH:MM, minimum of 10 minutes
#SBATCH -p serial_requeue   # Partition to submit to
#SBATCH --mem=60000           # Memory pool for all cores (see also --mem-per-cpu)
#SBATCH --array=0-26          # Memory pool for all cores (see also --mem-per-cpu)
#SBATCH -o ./job_out.yao_2021 # Standard output
#SBATCH -e ./job_out.yao_2021 # Standard error

BATCH_NUM=$SLURM_ARRAY_TASK_ID
H5AD_FILE=../00_prepare_dataset/processed/yao_2021.processed.h5ad
COV_FILE=../00_prepare_dataset/processed/yao_2021.cov.tsv

GS_FILE=gs_file/mouse.gs.batch/batch${BATCH_NUM}.gs

OUT_FOLDER=./score_file/yao_2021

mkdir -p ${OUT_FOLDER}

python3 /n/home11/mjzhang/gwas_informed_scRNAseq/scDRS/compute_score.py \
    --h5ad_file $H5AD_FILE\
    --h5ad_species mouse\
    --gs_file $GS_FILE\
    --gs_species mouse\
    --cov_file ${COV_FILE} \
    --flag_filter True\
    --flag_raw_count True\
    --flag_return_ctrl_raw_score False\
    --flag_return_ctrl_norm_score True\
    --out_folder $OUT_FOLDER