<!--# scDRS <!-- omit in toc -->

This variant of the scDRS package is altered to work with rat data instead of mouse. The scripts have been edited to reflect the change in species and to change the package name and any internal references to the package to "scdrs_rat" to prevent any issues with simultaneous installation alongside the original version. The homologs file has also be updated to swap mouse gene symbols for rat gene symbols and remove entries where no obvious rat homolog exists for the human gene. The rat gene list used here was obtained from the Rat Genome Database (https://rgd.mcw.edu/) on June 21, 2023. 

### Installation

    git clone https://github.com/CristLab/scDRS_Rat.git
    cd scDRS_Rat
    pip install -e .

### Usage

Usage instructions can be found at the main scDRS github respository and the scDRS github.io page linked below. Make sure to use "scdrs_rat" in place of "scdrs" for all usage.

### Original scDRS description, links, and reference

scDRS (single-cell disease-relevance score) is a method for associating individual cells in single-cell RNA-seq data with disease GWASs, built on top of [AnnData](https://anndata.readthedocs.io/en/latest/) and [Scanpy](https://scanpy.readthedocs.io/en/stable/). 

Read the [documentation](https://martinjzhang.github.io/scDRS/): [installation](https://martinjzhang.github.io/scDRS/index.html#installation), [usage](https://martinjzhang.github.io/scDRS/index.html#usage), [command-line interface (CLI)](https://martinjzhang.github.io/scDRS/reference_cli.html#), [file formats](https://martinjzhang.github.io/scDRS/file_format.html), etc. 

Check out [instructions](https://github.com/martinjzhang/scDRS/issues/2) for making customized gene sets using MAGMA. 

### Reference
[Zhang*, Hou*, et al. "Polygenic enrichment distinguishes disease associations of individual cells in single-cell RNA-seq data"](https://www.nature.com/articles/s41588-022-01167-z), Nature Genetics, 2022.


