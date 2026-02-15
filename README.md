# ABECluster: Behavior Patterns Powered Entity Clustering Framework in Account-based Blockchains

[![Blockchain: ETH/BSC](https://img.shields.io/badge/Blockchain-ETH%20%7C%20BSC-orange.svg)](#)

**ABECluster** is the first generalized two-stage entity clustering framework designed specifically for account-based blockchains (e.g., Ethereum, BSC). It bridges the gap between raw on-chain data and real-world entity identification by integrating advanced entity recognition and behavioral-based address clustering.

---

## 🚀 Overview

Public blockchains use address identities to achieve anonymity, posing challenges for transaction supervision. ABECluster overcomes the limitations of existing methods in attribute integration and efficiency through a two-stage approach:

1.  **Entity Recognition Stage**: Utilizes smart contract creation, ENS domains, and official labels. It features **EntityLLM**, a Large Language Model-based approach to bridge the semantic gap in blockchain-related short texts.
2.  **Address Clustering Stage**: Implements two novel, generalized heuristics (**Multi-Sender** and **Multi-Deposit**) based on real-world behavior patterns to group addresses belonging to the same entity.

---

## 📂 Repository Structure

The complete source code for the framework, including the EntityLLM modules and clustering heuristics, is now open-source. 

For a detailed walkthrough of the directory hierarchy and module descriptions, please refer to:
👉 [**projectStructure.md**](./projectStructure.md)

---

## 📊 Dataset

We provide an extensive on-chain deanonymized dataset constructed during our research, featuring over **102,375 entities** and **65,525,197 addresses**.

You can download the dataset here:
🔗 [**Google Drive - ABECluster Dataset**](https://drive.google.com/drive/folders/15GiFR9QSREiKyoMhwPfxz6DuHKzn4JL6)

*The dataset includes collected entities and phishing-related entities.*

---

## ✨ Key Features

* **Two-Stage Framework**: Combines semantic entity recognition with behavioral address clustering.
* **EntityLLM**: Leverages LLMs to identify hidden entity relationships in short-text data.
* **Address Clustering**: The first generalized clustering method in account-based blockchains.
* **High Efficiency**: Designed to handle large-scale data through subgraph disambiguation and node simplification, outperforming traditional clustering algorithms.
* **Cross-Chain Support**: Validated on both Ethereum (ETH) and Binance Smart Chain (BSC).

