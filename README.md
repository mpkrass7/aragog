# AutoRAG - OG

Welcome to the repo for the first repeatable attempt at AutoLM selection

## What is AutoRAG?

AutoRAG is a project that aims to automate the process of creating and deploying a QA Bot with all the functionality available within the DataRobot platform. This includes multiple basic RAG setups and vector stores as well as a few custom RAG setups. Each of these will be evaluated against a dataset of QA Pairs.

## Why AutoRAG

Do I even need to answer? DataRobot is the AutoML platform. Helping people pick the best language model is the next logical step in the process

## Getting started

1. Clone the repo
2. (recommended) Set up a virtual environment
3. `pip install -r requirements.txt`
4. Set credentials in `conf/local/credentials.yml`. An `example-credentials.yml` file has been provided
5. Set your project name in `conf/base/globals.yml`
6. `kedro run`