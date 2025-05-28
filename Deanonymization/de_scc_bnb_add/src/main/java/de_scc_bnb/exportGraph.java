package de_scc_bnb;

import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;
import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import java.io.*;
import java.util.*;

public class exportGraph {
    public static void main(String[] args) {
        JanusGraph graph = null;
        try {
            // 打开JanusGraph
            graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/de_scc_bnb_add/janusgraph-hbase-solr-proposed.properties");
            GraphTraversalSource g = graph.traversal();

            // 定义重要节点
            List<String> importantNodeIds = Arrays.asList(
                    "57c7b4f871588cbbbfa801cc1d2bcdcf40e2e44f",
                    "48eef733c868afcfcac66ba635e590aeb2956453",
                    "7ace54baa6e841797f1e85d0170483775be47aea",
                    "a93f0813ae6769828129d57632e3729f3f8120aa",
                    "d954551853f55deb4ae31407c423e67b1621424a"
                    );

            // 读取clustering.txt文件
            Set<String> clusteringNodeIds = new HashSet<>();

            // 跟踪节点和边的集合
            Set<String> outwardTraversalNodes = new HashSet<>(importantNodeIds);  // 从重要节点开始
            Set<String> inwardTraversalNodes = new HashSet<>();
            Map<String, String> nodeLabels = new HashMap<>();
            Map<String, Integer> nodeLayers = new HashMap<>(); // 添加层级映射
            Set<String> processedEdges = new HashSet<>();
            List<Map<String, String>> edgesList = new ArrayList<>();

            // 为重要节点设置标签和层级(Layer 2)
            for (String nodeId : importantNodeIds) {
                if (nodeId.equals("57c7b4f871588cbbbfa801cc1d2bcdcf40e2e44f")) {
                    nodeLabels.put(nodeId, "sourceNode");
                } else {
                    nodeLabels.put(nodeId, "imporNode");
                }
                nodeLayers.put(nodeId, 2); // 设置重要节点为Layer 2
            }

            System.out.println("开始正向遍历...");

            // 1. 第一层正向遍历 (outE().inV())
            Map<String, Integer> firstLevelNodeCounts = new HashMap<>();
            Set<String> allFirstLevelTargets = new HashSet<>(); // 记录所有发现的目标节点

            // 统计节点出现频率
            for (String sourceId : importantNodeIds) {
                try {
                    List<Vertex> vertices = g.V().has("bulkLoader.vertex.id", sourceId).outE().inV().dedup().toList();
                    for (Vertex vertex : vertices) {
                        String targetId = vertex.value("bulkLoader.vertex.id");
                        // 增加目标节点的计数
                        firstLevelNodeCounts.put(targetId, firstLevelNodeCounts.getOrDefault(targetId, 0) + 1);
                        allFirstLevelTargets.add(targetId);
                    }
                } catch (Exception e) {
                    System.err.println("第一层正向遍历节点 " + sourceId + " 时出错: " + e.getMessage());
                }
            }

            // 选择出现频率最高的前100个节点
            List<Map.Entry<String, Integer>> sortedNodes = new ArrayList<>(firstLevelNodeCounts.entrySet());
            sortedNodes.sort(Map.Entry.<String, Integer>comparingByValue().reversed());

            Set<String> firstLevelNodes = new HashSet<>();
            int limit = Math.min(20, sortedNodes.size());

            for (int i = 0; i < limit; i++) {
                String targetId = sortedNodes.get(i).getKey();
                firstLevelNodes.add(targetId);

                // 添加节点到遍历集合
                if (!outwardTraversalNodes.contains(targetId)) {
                    outwardTraversalNodes.add(targetId);
                    if (clusteringNodeIds.contains(targetId)) {
                        nodeLabels.put(targetId, "clusterNode");
                    } else {
                        nodeLabels.put(targetId, "otherNode");
                    }
                    nodeLayers.put(targetId, 3); // 设置正向第一层为Layer 3
                }

                // 为每个重要节点检查是否存在到该目标节点的边
                for (String importantNodeId : importantNodeIds) {
                    try {
                        List<Vertex> checkVertices = g.V().has("bulkLoader.vertex.id", importantNodeId).outE().inV().has("bulkLoader.vertex.id", targetId).toList();
                        if (!checkVertices.isEmpty()) {
                            // 存在从重要节点到目标节点的边
                            String edgeKey = importantNodeId + "->" + targetId;
                            if (!processedEdges.contains(edgeKey)) {
                                processedEdges.add(edgeKey);

                                Map<String, String> edge = new HashMap<>();
                                edge.put("source", importantNodeId);
                                edge.put("target", targetId);
                                edgesList.add(edge);
                            }
                        }
                    } catch (Exception e) {
                        System.err.println("检查边 " + importantNodeId + " -> " + targetId + " 时出错: " + e.getMessage());
                    }
                }
            }

            System.out.println("第一层正向遍历完成。选取了 " + firstLevelNodes.size() + " 个最频繁出现的节点。");

            // 2. 第二层正向遍历 (outE().inV())
            Map<String, Integer> secondLevelNodeCounts = new HashMap<>();
            Set<String> allSecondLevelTargets = new HashSet<>(); // 记录所有发现的目标节点

            for (String sourceId : firstLevelNodes) {
                try {
                    List<Vertex> vertices = g.V().has("bulkLoader.vertex.id", sourceId).outE().inV().dedup().toList();
                    for (Vertex vertex : vertices) {
                        String targetId = vertex.value("bulkLoader.vertex.id");
                        // 增加目标节点的计数
                        secondLevelNodeCounts.put(targetId, secondLevelNodeCounts.getOrDefault(targetId, 0) + 1);
                        allSecondLevelTargets.add(targetId);
                    }
                } catch (Exception e) {
                    System.err.println("第二层正向遍历节点 " + sourceId + " 时出错: " + e.getMessage());
                }
            }

            // 选择出现频率最高的前200个节点
            sortedNodes = new ArrayList<>(secondLevelNodeCounts.entrySet());
            sortedNodes.sort(Map.Entry.<String, Integer>comparingByValue().reversed());

            Set<String> secondLevelNodes = new HashSet<>();
            limit = Math.min(40, sortedNodes.size());

            for (int i = 0; i < limit; i++) {
                String targetId = sortedNodes.get(i).getKey();
                secondLevelNodes.add(targetId);

                // 添加节点到遍历集合（如果节点已访问过，跳过）
                if (!outwardTraversalNodes.contains(targetId)) {
                    outwardTraversalNodes.add(targetId);
                    if (clusteringNodeIds.contains(targetId)) {
                        nodeLabels.put(targetId, "clusterNode");
                    } else {
                        nodeLabels.put(targetId, "otherNode");
                    }
                    nodeLayers.put(targetId, 4); // 设置正向第二层为Layer 4
                }

                // 为每个第一层节点检查是否存在到该目标节点的边
                for (String firstLevelNodeId : firstLevelNodes) {
                    try {
                        List<Vertex> checkVertices = g.V().has("bulkLoader.vertex.id", firstLevelNodeId).outE().inV().has("bulkLoader.vertex.id", targetId).toList();
                        if (!checkVertices.isEmpty()) {
                            // 存在从第一层节点到目标节点的边
                            String edgeKey = firstLevelNodeId + "->" + targetId;
                            if (!processedEdges.contains(edgeKey)) {
                                processedEdges.add(edgeKey);

                                Map<String, String> edge = new HashMap<>();
                                edge.put("source", firstLevelNodeId);
                                edge.put("target", targetId);
                                edgesList.add(edge);
                            }
                        }
                    } catch (Exception e) {
                        System.err.println("检查边 " + firstLevelNodeId + " -> " + targetId + " 时出错: " + e.getMessage());
                    }
                }
            }

            System.out.println("正向遍历完成。总共收集了 " + outwardTraversalNodes.size() + " 个节点。");
            System.out.println("开始反向遍历...");

            // 3. 第一层反向遍历 (inE().outV())
            Map<String, Integer> firstLevelInwardNodeCounts = new HashMap<>();
            Set<String> allFirstLevelInwardSources = new HashSet<>(); // 记录所有发现的源节点

            for (String targetId : importantNodeIds) {
                try {
                    List<Vertex> vertices = g.V().has("bulkLoader.vertex.id", targetId).inE().outV().dedup().toList();
                    for (Vertex vertex : vertices) {
                        String sourceId = vertex.value("bulkLoader.vertex.id");
                        // 增加源节点的计数
                        firstLevelInwardNodeCounts.put(sourceId, firstLevelInwardNodeCounts.getOrDefault(sourceId, 0) + 1);
                        allFirstLevelInwardSources.add(sourceId);
                    }
                } catch (Exception e) {
                    System.err.println("第一层反向遍历节点 " + targetId + " 时出错: " + e.getMessage());
                }
            }

            // 选择出现频率最高的前100个节点
            List<Map.Entry<String, Integer>> sortedInwardNodes = new ArrayList<>(firstLevelInwardNodeCounts.entrySet());
            sortedInwardNodes.sort(Map.Entry.<String, Integer>comparingByValue().reversed());

            Set<String> firstLevelInwardNodes = new HashSet<>();
            int inwardLimit = Math.min(20, sortedInwardNodes.size());

            for (int i = 0; i < inwardLimit; i++) {
                String sourceId = sortedInwardNodes.get(i).getKey();
                String effectiveSourceId = sourceId;

                // 规则4逻辑: 根据节点之前出现的位置处理
                if (outwardTraversalNodes.contains(sourceId)) {
                    // 节点已在正向遍历中出现，如果未在反向遍历中出现，则添加，并修改ID
                    if (!inwardTraversalNodes.contains(sourceId)) {
                        effectiveSourceId = sourceId + "_1"; // 修改ID为sourceId_1
                        inwardTraversalNodes.add(sourceId);
                        firstLevelInwardNodes.add(sourceId);
                        if (clusteringNodeIds.contains(sourceId)) {
                            nodeLabels.put(effectiveSourceId, "clusterNode"); // 为新ID添加标签
                        } else {
                            nodeLabels.put(effectiveSourceId, "otherNode"); // 为新ID添加标签
                        }
                        nodeLayers.put(effectiveSourceId, 1); // 设置反向第一层为Layer 1
                    }
                } else if (!inwardTraversalNodes.contains(sourceId)) {
                    // 新节点，之前未在任何遍历中出现
                    inwardTraversalNodes.add(sourceId);
                    firstLevelInwardNodes.add(sourceId);
                    if (clusteringNodeIds.contains(sourceId)) {
                        nodeLabels.put(sourceId, "clusterNode");
                    } else {
                        nodeLabels.put(sourceId, "otherNode");
                    }
                    nodeLayers.put(sourceId, 1); // 设置反向第一层为Layer 1
                }

                // 为每个重要节点检查是否存在从该源节点到重要节点的边
                for (String importantNodeId : importantNodeIds) {
                    try {
                        List<Vertex> checkVertices = g.V().has("bulkLoader.vertex.id", sourceId).outE().inV().has("bulkLoader.vertex.id", importantNodeId).toList();
                        if (!checkVertices.isEmpty()) {
                            // 存在从源节点到重要节点的边
                            String edgeKey = effectiveSourceId + "->" + importantNodeId;
                            if (!processedEdges.contains(edgeKey)) {
                                processedEdges.add(edgeKey);

                                Map<String, String> edge = new HashMap<>();
                                edge.put("source", effectiveSourceId);
                                edge.put("target", importantNodeId);
                                edgesList.add(edge);
                            }
                        }
                    } catch (Exception e) {
                        System.err.println("检查边 " + effectiveSourceId + " -> " + importantNodeId + " 时出错: " + e.getMessage());
                    }
                }
            }

            System.out.println("第一层反向遍历完成。选取了 " + firstLevelInwardNodes.size() + " 个最频繁出现的节点。");

            // 4. 第二层反向遍历 (inE().outV())
            Map<String, Integer> secondLevelInwardNodeCounts = new HashMap<>();
            Set<String> allSecondLevelInwardSources = new HashSet<>(); // 记录所有发现的源节点

//            System.out.println(firstLevelInwardNodes);

            for (String targetId : firstLevelInwardNodes) {
                try {
//                    System.out.println(targetId);
                    List<Vertex> vertices = g.V().has("bulkLoader.vertex.id", targetId).inE().outV().dedup().toList();

//                    System.out.println(vertices);
                    for (Vertex vertex : vertices) {
                        String sourceId = vertex.value("bulkLoader.vertex.id");
                        // 增加源节点的计数
                        secondLevelInwardNodeCounts.put(sourceId, secondLevelInwardNodeCounts.getOrDefault(sourceId, 0) + 1);
                        allSecondLevelInwardSources.add(sourceId);
                    }
                } catch (Exception e) {
                    System.err.println("第二层反向遍历节点 " + targetId + " 时出错: " + e.getMessage());
                }
            }

            // 选择出现频率最高的前200个节点
            sortedInwardNodes = new ArrayList<>(secondLevelInwardNodeCounts.entrySet());
            sortedInwardNodes.sort(Map.Entry.<String, Integer>comparingByValue().reversed());

            inwardLimit = Math.min(40, sortedInwardNodes.size());


            System.out.println("11111111111111");
            for (int i = 0; i < inwardLimit; i++) {
                String sourceId = sortedInwardNodes.get(i).getKey();
                String effectiveSourceId = sourceId;

                // 规则4逻辑: 根据节点之前出现的位置处理
                if (outwardTraversalNodes.contains(sourceId)) {
                    // 节点已在正向遍历中出现，如果未在反向遍历中出现，则添加，并修改ID
                    if (!inwardTraversalNodes.contains(sourceId)) {
                        effectiveSourceId = sourceId + "_1"; // 修改ID为sourceId_1
                        inwardTraversalNodes.add(sourceId);
                        if (clusteringNodeIds.contains(sourceId)) {
                            nodeLabels.put(effectiveSourceId, "clusterNode"); // 为新ID添加标签
                        } else {
                            nodeLabels.put(effectiveSourceId, "otherNode"); // 为新ID添加标签
                        }
                        nodeLayers.put(effectiveSourceId, 0); // 设置反向第二层为Layer 0
                    }
                } else if (!inwardTraversalNodes.contains(sourceId)) {
                    // 新节点，之前未在任何遍历中出现
                    inwardTraversalNodes.add(sourceId);
                    if (clusteringNodeIds.contains(sourceId)) {
                        nodeLabels.put(sourceId, "clusterNode");
                    } else {
                        nodeLabels.put(sourceId, "otherNode");
                    }
                    nodeLayers.put(sourceId, 0); // 设置反向第二层为Layer 0
                }

                // 为每个第一层反向遍历的节点检查是否存在从该源节点到它的边
                for (String firstLevelInwardNodeId : firstLevelInwardNodes) {
                    try {
                        System.out.println(sourceId);
                        System.out.println(firstLevelInwardNodeId);
//                        List<Vertex> checkVertices = g.V().has("bulkLoader.vertex.id", sourceId).outE().inV().has("bulkLoader.vertex.id", firstLevelInwardNodeId).dedup().toList();
                        List<Vertex> checkVertices = g.V().has("bulkLoader.vertex.id", firstLevelInwardNodeId).inE().outV().has("bulkLoader.vertex.id", sourceId).dedup().toList();
                        System.out.println(checkVertices);
                        if (!checkVertices.isEmpty()) {
                            // 存在从源节点到第一层反向节点的边
                            String edgeKey = effectiveSourceId + "->" + firstLevelInwardNodeId;
                            if (!processedEdges.contains(edgeKey)) {
                                processedEdges.add(edgeKey);

                                Map<String, String> edge = new HashMap<>();
                                edge.put("source", effectiveSourceId);
                                edge.put("target", firstLevelInwardNodeId);
                                edgesList.add(edge);
                            }
                        }
                    } catch (Exception e) {
                        System.err.println("检查边 " + effectiveSourceId + " -> " + firstLevelInwardNodeId + " 时出错: " + e.getMessage());
                        e.printStackTrace();
                    }
                }
            }

            System.out.println("反向遍历完成。反向遍历中总节点数: " + inwardTraversalNodes.size());

            // 创建最终的节点列表用于导出
            List<Map<String, String>> nodesList = new ArrayList<>();
            Set<String> addedNodes = new HashSet<>(); // 跟踪已添加的节点ID

            for (Map.Entry<String, String> entry : nodeLabels.entrySet()) {
                String nodeId = entry.getKey();
                String label = entry.getValue();

                // 避免添加重复的基本节点（不带_1后缀的节点）
                if (nodeId.contains("_1") || !addedNodes.contains(nodeId)) {
                    Map<String, String> node = new HashMap<>();
                    node.put("id", nodeId);
                    node.put("label", label);
                    // 添加layer属性
                    Integer layer = nodeLayers.getOrDefault(nodeId, -1); // 如果没有层级信息则设为-1
                    node.put("layer", String.valueOf(layer));
                    nodesList.add(node);
                    addedNodes.add(nodeId);
                }
            }

            // 导出结果为JSON
            exportToJson(nodesList, edgesList);

            System.out.println("处理成功完成。");

        } catch (Exception e) {
            System.err.println("错误: " + e.getMessage());
            e.printStackTrace();
        } finally {
            if (graph != null) {
                try {
                    graph.close();
                } catch (Exception e) {
                    System.err.println("关闭图时出错: " + e.getMessage());
                }
            }
        }
    }

    private static Set<String> readClusteringFile() {
        Set<String> clusteringNodeIds = new HashSet<>();
        try (BufferedReader reader = new BufferedReader(new FileReader("/public/home/blockchain_2/slave2/deanonymization/de_scc_bnb_add/cluster/times.txt"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] nodeIds = line.split(",");
                for (String nodeId : nodeIds) {
                    clusteringNodeIds.add(nodeId.trim());
                }
            }
            System.out.println("从clustering.txt读取了 " + clusteringNodeIds.size() + " 个节点");
        } catch (IOException e) {
            System.err.println("读取clustering.txt文件时出错: " + e.getMessage());
        }
        return clusteringNodeIds;
    }

    private static void exportToJson(List<Map<String, String>> nodes, List<Map<String, String>> edges) {
        try {
            StringBuilder json = new StringBuilder();
            json.append("{\n");

            // 添加节点，包含layer属性
            json.append("  \"nodes\": [\n");
            for (int i = 0; i < nodes.size(); i++) {
                Map<String, String> node = nodes.get(i);
                json.append("    {\"id\": \"").append(node.get("id")).append("\", \"label\": \"")
                        .append(node.get("label")).append("\", \"layer\": ").append(node.get("layer")).append("}");
                if (i < nodes.size() - 1) {
                    json.append(",");
                }
                json.append("\n");
            }
            json.append("  ],\n");

            // 添加边
            json.append("  \"edges\": [\n");
            for (int i = 0; i < edges.size(); i++) {
                Map<String, String> edge = edges.get(i);
                json.append("    {\"source\": \"").append(edge.get("source")).append("\", \"target\": \"").append(edge.get("target")).append("\"}");
                if (i < edges.size() - 1) {
                    json.append(",");
                }
                json.append("\n");
            }
            json.append("  ]\n");

            json.append("}");

            // 写入JSON文件
            try (FileWriter writer = new FileWriter("graph_data_20_40.json")) {
                writer.write(json.toString());
                System.out.println("成功将图数据写入graph_data.json");
                System.out.println("导出了 " + nodes.size() + " 个节点和 " + edges.size() + " 条边");
            }
        } catch (IOException e) {
            System.err.println("写入JSON文件时出错: " + e.getMessage());
        }
    }
}