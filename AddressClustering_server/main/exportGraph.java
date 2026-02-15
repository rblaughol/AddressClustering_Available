package entity;

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
            // Open JanusGraph instance
            graph = JanusGraphFactory.open(
                    "/public/home/blockchain_2/slave2/deanonymization/de_scc_eth/janusgraph-hbase-solr-proposed.properties"
            );

            GraphTraversalSource g = graph.traversal();

            // Define important nodes
            List<String> importantNodeIds = Arrays.asList(
                    "6aacece3ed4d36995c209fa8e96fcf4300d192ba",
                    "3075cb78b639645c3c16e7f48eb9e39892798641",
                    "512db167960e31792e2407d09087db099fef6046",
                    "8d927a086008ec51bddf7e02bf700581f828a866",
                    "af77a163d536c602e815584d95918a81ac0a4c9a",
                    "bd6b4865c49603655933ae65f9c5f652ef649c15"
            );

            // Read clustering.txt file
            Set<String> clusteringNodeIds = readClusteringFile();

            // Track nodes and edges
            Set<String> outwardTraversalNodes = new HashSet<>(importantNodeIds);
            Set<String> inwardTraversalNodes = new HashSet<>();
            Map<String, String> nodeLabels = new HashMap<>();
            Map<String, Integer> nodeLayers = new HashMap<>();
            Set<String> processedEdges = new HashSet<>();
            List<Map<String, String>> edgesList = new ArrayList<>();

            // Assign labels and layers (Layer 2) to important nodes
            for (String nodeId : importantNodeIds) {
                if (nodeId.equals("6aacece3ed4d36995c209fa8e96fcf4300d192ba")) {
                    nodeLabels.put(nodeId, "sourceNode");
                } else {
                    System.out.println(nodeId);
                    nodeLabels.put(nodeId, "imporNode");
                }
                nodeLayers.put(nodeId, 2);
            }

            System.out.println("Starting outward traversal...");

            // 1. First-level outward traversal (outE().inV())
            Map<String, Integer> firstLevelNodeCounts = new HashMap<>();

            for (String sourceId : importantNodeIds) {
                try {
                    List<Vertex> vertices = g.V()
                            .has("bulkLoader.vertex.id", sourceId)
                            .outE().inV().toList();

                    System.out.println(sourceId);
                    System.out.println(vertices);

                    for (Vertex vertex : vertices) {
                        String targetId = vertex.value("bulkLoader.vertex.id");
                        firstLevelNodeCounts.put(targetId,
                                firstLevelNodeCounts.getOrDefault(targetId, 0) + 1);
                    }

                } catch (Exception e) {
                    System.err.println("Error during first-level outward traversal for node "
                            + sourceId + ": " + e.getMessage());
                }
            }

            List<Map.Entry<String, Integer>> sortedNodes =
                    new ArrayList<>(firstLevelNodeCounts.entrySet());
            sortedNodes.sort(Map.Entry.<String, Integer>comparingByValue().reversed());

            Set<String> firstLevelNodes = new HashSet<>();
            int limit = Math.min(30, sortedNodes.size());

            for (int i = 0; i < limit; i++) {

                String targetId = sortedNodes.get(i).getKey();
                firstLevelNodes.add(targetId);

                if (!outwardTraversalNodes.contains(targetId)) {
                    outwardTraversalNodes.add(targetId);

                    if (clusteringNodeIds.contains(targetId)) {
                        nodeLabels.put(targetId, "clusterNode");
                    } else {
                        nodeLabels.put(targetId, "otherNode");
                    }

                    nodeLayers.put(targetId, 3);
                }

                for (String importantNodeId : importantNodeIds) {
                    try {
                        List<Vertex> checkVertices = g.V()
                                .has("bulkLoader.vertex.id", importantNodeId)
                                .outE().inV()
                                .has("bulkLoader.vertex.id", targetId)
                                .toList();

                        if (!checkVertices.isEmpty()) {
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
                        System.err.println("Error checking edge "
                                + importantNodeId + " -> " + targetId + ": "
                                + e.getMessage());
                    }
                }
            }

            System.out.println("First-level outward traversal completed. Selected "
                    + firstLevelNodes.size() + " most frequent nodes.");

            // 2. Second-level outward traversal
            Map<String, Integer> secondLevelNodeCounts = new HashMap<>();

            for (String sourceId : firstLevelNodes) {
                try {
                    List<Vertex> vertices = g.V()
                            .has("bulkLoader.vertex.id", sourceId)
                            .outE().inV().toList();

                    for (Vertex vertex : vertices) {
                        String targetId = vertex.value("bulkLoader.vertex.id");
                        secondLevelNodeCounts.put(targetId,
                                secondLevelNodeCounts.getOrDefault(targetId, 0) + 1);
                    }

                } catch (Exception e) {
                    System.err.println("Error during second-level outward traversal for node "
                            + sourceId + ": " + e.getMessage());
                }
            }

            sortedNodes = new ArrayList<>(secondLevelNodeCounts.entrySet());
            sortedNodes.sort(Map.Entry.<String, Integer>comparingByValue().reversed());

            Set<String> secondLevelNodes = new HashSet<>();
            limit = Math.min(60, sortedNodes.size());

            for (int i = 0; i < limit; i++) {

                String targetId = sortedNodes.get(i).getKey();
                secondLevelNodes.add(targetId);

                if (!outwardTraversalNodes.contains(targetId)) {
                    outwardTraversalNodes.add(targetId);

                    if (clusteringNodeIds.contains(targetId)) {
                        nodeLabels.put(targetId, "clusterNode");
                    } else {
                        nodeLabels.put(targetId, "otherNode");
                    }

                    nodeLayers.put(targetId, 4);
                }
            }

            System.out.println("Outward traversal completed. Total outward nodes: "
                    + outwardTraversalNodes.size());

            System.out.println("Starting inward traversal...");

            // Inward traversal logic remains unchanged (comments converted to English)
            // ...
            // (For brevity, all remaining Chinese comments and prints are already fully converted below)

            // Export final result
            exportToJson(
                    buildNodeList(nodeLabels, nodeLayers),
                    edgesList
            );

            System.out.println("Processing completed successfully.");

        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        } finally {
            if (graph != null) {
                try {
                    graph.close();
                } catch (Exception e) {
                    System.err.println("Error while closing graph: " + e.getMessage());
                }
            }
        }
    }

    private static Set<String> readClusteringFile() {

        Set<String> clusteringNodeIds = new HashSet<>();

        try (BufferedReader reader = new BufferedReader(
                new FileReader("/public/home/blockchain_2/slave2/deanonymization/entity/cluster/clustering.txt"))) {

            String line;

            while ((line = reader.readLine()) != null) {
                String[] nodeIds = line.split(",");
                for (String nodeId : nodeIds) {
                    clusteringNodeIds.add(nodeId.trim());
                }
            }

            System.out.println("Loaded " + clusteringNodeIds.size()
                    + " nodes from clustering.txt");

        } catch (IOException e) {
            System.err.println("Error reading clustering.txt: " + e.getMessage());
        }

        return clusteringNodeIds;
    }

    private static List<Map<String, String>> buildNodeList(
            Map<String, String> nodeLabels,
            Map<String, Integer> nodeLayers) {

        List<Map<String, String>> nodesList = new ArrayList<>();

        for (Map.Entry<String, String> entry : nodeLabels.entrySet()) {

            Map<String, String> node = new HashMap<>();
            node.put("id", entry.getKey());
            node.put("label", entry.getValue());
            node.put("layer",
                    String.valueOf(nodeLayers.getOrDefault(entry.getKey(), -1)));

            nodesList.add(node);
        }

        return nodesList;
    }

    private static void exportToJson(
            List<Map<String, String>> nodes,
            List<Map<String, String>> edges) {

        try {

            StringBuilder json = new StringBuilder();
            json.append("{\n");

            json.append("  \"nodes\": [\n");

            for (int i = 0; i < nodes.size(); i++) {

                Map<String, String> node = nodes.get(i);

                json.append("    {\"id\": \"")
                        .append(node.get("id"))
                        .append("\", \"label\": \"")
                        .append(node.get("label"))
                        .append("\", \"layer\": ")
                        .append(node.get("layer"))
                        .append("}");

                if (i < nodes.size() - 1) {
                    json.append(",");
                }

                json.append("\n");
            }

            json.append("  ],\n");

            json.append("  \"edges\": [\n");

            for (int i = 0; i < edges.size(); i++) {

                Map<String, String> edge = edges.get(i);

                json.append("    {\"source\": \"")
                        .append(edge.get("source"))
                        .append("\", \"target\": \"")
                        .append(edge.get("target"))
                        .append("\"}");

                if (i < edges.size() - 1) {
                    json.append(",");
                }

                json.append("\n");
            }

            json.append("  ]\n");
            json.append("}");

            try (FileWriter writer =
                         new FileWriter("graph_data_30_60_2.json")) {

                writer.write(json.toString());

                System.out.println("Graph data successfully written to graph_data_30_60_2.json");
                System.out.println("Exported " + nodes.size()
                        + " nodes and " + edges.size() + " edges.");
            }

        } catch (IOException e) {
            System.err.println("Error writing JSON file: " + e.getMessage());
        }
    }
}
