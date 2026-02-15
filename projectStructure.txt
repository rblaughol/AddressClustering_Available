├── AddressClustering_py/ 
│   ├── Address_clustering.py       # Main entry point for the clustering process
│   ├── utils/
│   │   ├── heuristics.py           # Implementation of the two specific heuristic algorithms (SG1 & SG2)
│   │   ├── rpc_client.py           # RPC client for querying transaction history of specific addresses
│   │   ├── tools.py                # General utility functions and logging tools
├── AddressClustering_server/ 
│   ├── application_results/        # Application results
│   ├── baseline/                   # Implementation of reproduced baseline algorithms
│   │   ├── BSC/
│   │   │   ├── Other Directories   # Baseline results
│   │   ├── ETH/                    # Implementation of reproduced baseline algorithms
│   │   │   ├── Other Directories   # Baseline results
│   ├── main/                       
│   │   ├── SG1_dec.java            # SG1 Implementation
│   │   ├── SG2_dec.java            # SG2 Implementation
│   │   ├── clustering.py           # Cluster with entity results
│   │   ├── dec.java                # Main entry point for the clustering process
├── EntityRecognition/
│   ├── ENS/
│   │   ├── dataset/
│   │   │   ├── preprocess_ens.py   # Prepocess the dataset
│   │   ├── EntityLLM/
│   │   │   ├── entityLLM.py        # Main pipeline
│   │   │   ├── qwen_kmeans_clustering.py   # Generates embeddings for ENS and labels, followed by K-means clustering
│   │   │   ├── readme.txt
│   │   │   ├── repair_address.py
│   │   │   ├── repair_address_retry.py
│   │   ├── realtime_update/    # Real time update method
│   │   │   ├── ens_obtain.py   # Real time update method (incremental dataset)
│   ├── evaluate/
│   │   ├── ens_instance_instruction.py
│   │   ├── ens_pair_wise.py
│   │   ├── label_instance_instruction.py
│   │   ├── label_pair_wise.py
│   │   ├── preprocess.py
│   │   ├── baseline/
│   │   │   ├── embedding/         
│   │   │   │   ├── generate_entity_clusters.py         # Performs clustering based on the generated text embeddings  
│   │   │   │   ├── run_vectorization.py                # Main entry point for generating text embeddings
│   │   │   │   ├── translate_clusters.py               # Converts addresses in the clustering results into their corresponding label text
│   │   │   │   ├── vectorization.py                    # Utility functions for embedding; defines methods to invoke various embedding models
│   │   │   ├── LLM_based/
│   │   │   │   ├── blocking.py                         # Performs initial coarse screening (blocking) of data
│   │   │   │   ├── filtering.py                        # Performs secondary filtering of the data
│   │   │   │   ├── preprocess.py                       # Data cleaning script
│   │   │   │   ├── run_pipeline.py                     # Main entry point for the overall pipeline execution
│   │   │   │   ├── selecting.py                        # Uses LLM to evaluate/judge the filtered data
│   │   │   │   ├── utils.py                            # Utility functions
│   ├── Label/
│   │   ├── dataset/
│   │   │   ├── preprocess_label.py # Prepocess the dataset
│   │   ├── EntityLLM/
│   │   │   ├── class4LLM.py    # Main pipeline 1
│   │   │   ├── entityLLM.py    # Main pipeline 2
│   │   │   ├── qwen_kmeans_clustering.py   # Generates embeddings for ENS and labels, followed by K-means clustering
│   │   │   ├── repair_address.py
│   │   ├── realtime_update/    # Real time update method (incremental dataset)
│   │   │   ├── label_crawler1.py   # Crawler #1
│   │   │   ├── label_crawler2.py   # Crawler #2
│   ├── SCC/
│   │   ├── analysis/
│   │   │   ├── phishing_related.py     # Phishing related addresses
│   │   │   ├── powerlaw_dis.py         # Powerlaw fitting
│   │   ├── dataset/                    # Process and generate the dataset
│   │   ├── realtime_update/
│   │   │   ├── contract_create.py      # Real time update method (incremental dataset)
