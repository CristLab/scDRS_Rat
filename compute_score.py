import scanpy as sc
from anndata import read_h5ad
import pandas as pd
import numpy as np
import scipy as sp
import os
import time
import argparse
from statsmodels.stats.multitest import multipletests

# Inhouse tools
import scdrs.util as util
import scdrs.data_loader as dl
import scdrs.method as md
import scdrs.sparse_util as sparse_util

"""
# Fixit


# Todo
- Implement a memory efficient version
- Implement scdrs.method.proprocess to incorporate sparse_reg_out and sparse_compute_stats
- "gene_weight" argument needs to be tested 
- Check the situation where df_cov does not explicitly contain "const" but contains a linear combinition of const

# Finished
- Add --n_ctrl (default value 500) 
- Add --cov_file option to regress out covariates stored in COV_FILE before feeding into the score function 
- Add --ctrl_match_opt='mean_var': use mean- and var- matched control genes 
- Change name from scTRS to scdrs (072721)
- Fixed: Warning for compute_score: Trying to set attribute `.X` of view, copying. (did: v_norm_score = v_raw_score.copy())

"""

VERSION = "0.0.1"
VERSION = "beta"


def convert_species_name(species):
    if species in ["Mouse", "mouse", "Mus_musculus", "mus_musculus", "mmusculus"]:
        return "mmusculus"
    if species in ["Human", "human", "Homo_sapiens", "homo_sapiens", "hsapiens"]:
        return "hsapiens"
    raise ValueError("# compute_score: species name %s not supported" % species)


def main(args):
    sys_start_time = time.time()

    MASTHEAD = "******************************************************************************\n"
    MASTHEAD += "* Single-cell disease relevance score (scDRS)\n"
    MASTHEAD += "* Version %s\n" % VERSION
    MASTHEAD += "* Martin Jinye Zhang and Kangcheng Hou\n"
    MASTHEAD += "* HSPH / Broad Institute / UCLA\n"
    MASTHEAD += "* MIT License\n"
    MASTHEAD += "******************************************************************************\n"

    ###########################################################################################
    ######                                    Parse Options                              ######
    ###########################################################################################
    H5AD_FILE = args.h5ad_file
    H5AD_SPECIES = args.h5ad_species
    COV_FILE = args.cov_file
    GS_FILE = args.gs_file
    GS_SPECIES = args.gs_species
    CTRL_MATCH_OPT = args.ctrl_match_opt
    WEIGHT_OPT = args.weight_opt
    FLAG_FILTER = args.flag_filter == "True"
    FLAG_RAW_COUNT = args.flag_raw_count == "True"
    N_CTRL = int(args.n_ctrl)
    FLAG_RETURN_CTRL_RAW_SCORE = args.flag_return_ctrl_raw_score == "True"
    FLAG_RETURN_CTRL_NORM_SCORE = args.flag_return_ctrl_norm_score == "True"
    FLAG_SPARSE = args.flag_sparse == "True"
    OUT_FOLDER = args.out_folder

    if H5AD_SPECIES != GS_SPECIES:
        H5AD_SPECIES = convert_species_name(H5AD_SPECIES)
        GS_SPECIES = convert_species_name(GS_SPECIES)

    header = MASTHEAD
    header += "Call: ./compute_score.py \\\n"
    header += "--h5ad_file %s\\\n" % H5AD_FILE
    header += "--h5ad_species %s\\\n" % H5AD_SPECIES
    header += "--cov_file %s\\\n" % COV_FILE
    header += "--gs_file %s\\\n" % GS_FILE
    header += "--gs_species %s\\\n" % GS_SPECIES
    header += "--ctrl_match_opt %s\\\n" % CTRL_MATCH_OPT
    header += "--weight_opt %s\\\n" % WEIGHT_OPT
    header += "--flag_filter %s\\\n" % FLAG_FILTER
    header += "--flag_raw_count %s\\\n" % FLAG_RAW_COUNT
    header += "--n_ctrl %d\\\n" % N_CTRL
    header += "--flag_return_ctrl_raw_score %s\\\n" % FLAG_RETURN_CTRL_RAW_SCORE
    header += "--flag_return_ctrl_norm_score %s\\\n" % FLAG_RETURN_CTRL_NORM_SCORE
    header += "--out_folder %s\n" % OUT_FOLDER
    print(header)

    # Check options
    if H5AD_SPECIES != GS_SPECIES:
        if H5AD_SPECIES not in ["mmusculus", "hsapiens"]:
            raise ValueError(
                "--h5ad_species needs to be one of [mmusculus, hsapiens] "
                "unless --h5ad_species==--gs_species"
            )
        if GS_SPECIES not in ["mmusculus", "hsapiens"]:
            raise ValueError(
                "--gs_species needs to be one of [mmusculus, hsapiens] "
                "unless --h5ad_species==--gs_species"
            )
    if CTRL_MATCH_OPT not in ["mean", "mean_var"]:
        raise ValueError("--ctrl_match_opt needs to be one of [mean, mean_var]")
    if WEIGHT_OPT not in ["uniform", "vs", "od"]:
        raise ValueError("--weight_opt needs to be one of [uniform, vs, inv_std, od]")

    ###########################################################################################
    ######                                     Load data                                 ######
    ###########################################################################################
    print("Load data:")

    # Load .h5ad file
    adata = read_h5ad(H5AD_FILE)
    if FLAG_FILTER:
        sc.pp.filter_cells(adata, min_genes=250)
        sc.pp.filter_genes(adata, min_cells=50)
    if FLAG_RAW_COUNT:
        sc.pp.normalize_per_cell(adata, counts_per_cell_after=1e4)
        sc.pp.log1p(adata)
    print(
        "--h5ad_file loaded: n_cell=%d, n_gene=%d (sys_time=%0.1fs)"
        % (adata.shape[0], adata.shape[1], time.time() - sys_start_time)
    )

    # adata = adata[0:500,:].copy()

    # Load .cov file and regress out covariates
    # fixit: integrate regout with compute score
    # fixit: add const if it does not exist
    if COV_FILE is not None:
        df_cov = pd.read_csv(COV_FILE, sep="\t", index_col=0)
        cov_list = list(df_cov.columns)
        if len(set(df_cov.index) & set(adata.obs_names)) < 0.1 * adata.shape[0]:
            raise ValueError("--cov_file does not match the cells in --h5ad_file")
        adata.obs.drop(
            [x for x in cov_list if x in adata.obs.columns], axis=1, inplace=True
        )
        adata.obs = adata.obs.join(df_cov)
        adata.obs.fillna(adata.obs[cov_list].mean(), inplace=True)
        # fixit: add const if it is not there
        v_resid = md.reg_out(np.ones(adata.shape[0]), adata.obs[cov_list])
        if ((v_resid ** 2).mean() > 0.05) and ("const" not in cov_list):
            adata.obs["const"] = 1
            cov_list = ["const"] + cov_list
        # fixit
        print(
            "--cov_file loaded: covariates=[%s] (sys_time=%0.1fs)"
            % (", ".join(cov_list), time.time() - sys_start_time)
        )

        if FLAG_SPARSE:
            # if adata not csr_matrix, enforce adata.X to be csr_matrix
            if not isinstance(adata.X, sp.sparse.csr_matrix):
                adata.X = sp.sparse.csr_matrix(adata.X)
                print("FLAG_SPARSE=True, enforcing adata.X to be sp.sparse.csr_matrix")

        if FLAG_SPARSE == False:  # fixit: if FLAG_SPARSE is probably better
            adata.var["mean"] = adata.X.mean(axis=0).T
            if sp.sparse.issparse(adata.X):
                adata.X = adata.X.toarray()
            adata.X -= adata.var["mean"].values
            adata.X = md.reg_out(adata.X, adata.obs[cov_list].values)
            adata.X += adata.var["mean"]
            print(
                "Regress out covariates from --h5ad_file (sys_time=%0.1fs)"
                % (time.time() - sys_start_time)
            )
        else:
            # assert first column of covariates must be all 1s
            # fixit: add 1 if the cov_file doesn't have this
            cov_values = adata.obs[cov_list].values
            assert np.all(
                cov_values[:, 0] == 1
            ), "FLAG_SPARSE=True, First column of covariates must be all 1s, insert an intercept if there isn't one"
            sparse_util.sparse_reg_out(adata, cov_values)
            print(
                "FLAG_SPARSE=True, regress out covariates from --h5ad_file (sys_time=%0.1fs)"
                % (time.time() - sys_start_time)
            )

    # Load .gs file, convert species if needed and merge with adata.var_names
    dict_gs = util.load_gs(
        GS_FILE,
        src_species=GS_SPECIES,
        dst_species=H5AD_SPECIES,
        to_intersect=adata.var_names,
    )
    print(
        "--gs_file loaded: n_geneset=%d (sys_time=%0.1fs)"
        % (len(dict_gs), time.time() - sys_start_time)
    )

    ###########################################################################################
    ######                                  Computation                                  ######
    ###########################################################################################

    # Compute statistics, including the 20*20 mean-var bins
    print("Compute cell-level and gene-level statistics:")
    if FLAG_SPARSE == False:
        md.compute_stats(adata)
    else:
        sparse_util.sparse_compute_stats(
            adata
        )  # fixit: this depends on adata.uns['_SCDRS_SPARSE']
    print("")

    # Compute score
    print("Compute score:")
    for trait in dict_gs:
        gene_list, gene_weights = dict_gs[trait]
        if len(gene_list) < 10:
            print(
                "trait=%s: skipped due to small size (n_gene=%d, sys_time=%0.1fs)"
                % (trait, len(gene_list), time.time() - sys_start_time)
            )
            continue

        df_res = md.score_cell(
            adata,
            gene_list,
            gene_weight=gene_weights,
            ctrl_match_key=CTRL_MATCH_OPT,
            n_ctrl=N_CTRL,
            weight_opt=WEIGHT_OPT,
            return_ctrl_raw_score=FLAG_RETURN_CTRL_RAW_SCORE,
            return_ctrl_norm_score=FLAG_RETURN_CTRL_NORM_SCORE,
            verbose=False,
            sparse=FLAG_SPARSE,
        )
        df_res.iloc[:, 0:6].to_csv(
            os.path.join(OUT_FOLDER, "%s.score.gz" % trait),
            sep="\t",
            index=True,
            compression="gzip",
        )
        if FLAG_RETURN_CTRL_RAW_SCORE | FLAG_RETURN_CTRL_NORM_SCORE:
            df_res.to_csv(
                os.path.join(OUT_FOLDER, "%s.full_score.gz" % trait),
                sep="\t",
                index=True,
                compression="gzip",
            )
        v_fdr = multipletests(df_res["pval"].values, method="fdr_bh")[1]
        n_rej_01 = (v_fdr < 0.1).sum()
        n_rej_02 = (v_fdr < 0.2).sum()
        print(
            "Gene set %s (n_gene=%d): %d/%d FDR<0.1 cells, %d/%d FDR<0.2 cells (sys_time=%0.1fs)"
            % (
                trait,
                len(gene_list),
                n_rej_01,
                df_res.shape[0],
                n_rej_02,
                df_res.shape[0],
                time.time() - sys_start_time,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="compute score")

    parser.add_argument("--h5ad_file", type=str, required=True)
    parser.add_argument(
        "--h5ad_species", type=str, required=True, help="one of [hsapiens, mmusculus]"
    )
    parser.add_argument("--cov_file", type=str, required=False, default=None)
    parser.add_argument("--gs_file", type=str, required=True)
    parser.add_argument(
        "--gs_species", type=str, required=True, help="one of [hsapiens, mmusculus]"
    )
    parser.add_argument(
        "--ctrl_match_opt", type=str, required=False, default="mean_var"
    )
    parser.add_argument("--weight_opt", type=str, required=False, default="vs")
    parser.add_argument(
        "--flag_sparse",
        type=str,
        required=False,
        default="False",
        help="If to use a sparse implementation, which leverages the sparsity of the data."
        "The appropriate usage place would be a highly sparse count matrix in adata, and one need to correct for covarates",
    )
    parser.add_argument(
        "--flag_filter",
        type=str,
        required=False,
        default="True",
        help="If to apply cell and gene filters to the h5ad_file data",
    )
    parser.add_argument(
        "--flag_raw_count",
        type=str,
        required=False,
        default="True",
        help="If True, apply size factor normalization and log1p transformation",
    )
    parser.add_argument(
        "--n_ctrl",
        type=int,
        required=False,
        default=1000,
        help="Number of control genes",
    )
    parser.add_argument(
        "--flag_return_ctrl_raw_score",
        type=str,
        required=False,
        default="False",
        help="If True, return raw control scores",
    )
    parser.add_argument(
        "--flag_return_ctrl_norm_score",
        type=str,
        required=False,
        default="False",
        help="If True, return normalized control scores",
    )
    parser.add_argument(
        "--out_folder",
        type=str,
        required=True,
        help="Save file at out_folder/trait.score.gz",
    )

    args = parser.parse_args()

    main(args)