package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;
import java.math.BigInteger;
import java.util.*;
import java.util.stream.Collectors;
import java.io.*;

public class deposit_token {
    private static BigInteger dynamicThreshold = new BigInteger("10");
    private static Set<String> exchangeAddresses = new HashSet<>();
    private static Set<String> minerAddresses = new HashSet<>();
    private static Set<Set<Vertex>> matchedGroups = new HashSet<>();

    static {
        loadAddressData("exchanges.csv", exchangeAddresses);
        loadAddressData("miners_eth.txt", minerAddresses);
    }

    public static void main(String[] args) {
        JanusGraph graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();
        
        // Read address list from file
        List<String> addresses = readAddressesFromFile("Tokenadd.txt");
        String outputDir = "Tokenadd_deposit_token/";
        new File(outputDir).mkdirs();

        for (int i = 0; i < addresses.size(); i++) {
            String clusterAdd = addresses.get(i);
            matchedGroups.clear(); // Clear previous matching results

            // Process each DV address
            List<Object> DVs = g.V().has("bulkLoader.vertex.id", clusterAdd)
                                 .bothE().values("source_address").dedup().toList();
            for (Object dv : DVs) {
                processInitAddress(clusterAdd, g, "TT", dv.toString(), true);
            }

            // Get and write weakly connected component
            Vertex initVertex = g.V().has("bulkLoader.vertex.id", clusterAdd).next();
            Set<Vertex> wcc = findWeaklyConnectedComponent(initVertex, matchedGroups);
            writeWCCToFile(wcc, outputDir + clusterAdd + ".out");
        }
        
        graph.close();
    }

    // New method: batch read address file
    private static List<String> readAddressesFromFile(String filename) {
        List<String> addresses = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(filename))) {
            String line;
            while ((line = br.readLine()) != null) {
                addresses.add(line.trim());
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        return addresses;
    }

    // Original method unchanged
    private static void loadAddressData(String filename, Set<String> targetSet) {
        try (BufferedReader br = new BufferedReader(new FileReader(filename))) {
            String line;
            boolean isCSV = filename.endsWith(".csv");
            if (isCSV) br.readLine(); // Skip CSV header
            
            while ((line = br.readLine()) != null) {
                String address = isCSV ? line.split(",")[0].trim() : line.trim();
                targetSet.add(address.toLowerCase());
            }
            System.out.println("Loaded " + targetSet.size() + " addresses from " + filename);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public static Set<Set<Vertex>> processInitAddress(String address, GraphTraversalSource g, String BH, String sourceAddress, boolean strict) {
        try {
            Vertex initVertex = g.V().has("bulkLoader.vertex.id", address).next();
            List<Edge> initOutEdges;

            if (sourceAddress.equals("None")) {
                initOutEdges = g.V(initVertex).outE().toList().stream()
                    .filter(edge -> !"TT".equals(edge.value("behaviour2")) && 
                           !new BigInteger(edge.value("value").toString()).equals(BigInteger.ZERO))
                    .collect(Collectors.toList());
            } else {
                initOutEdges = g.V(initVertex).outE()
                    .has("behaviour2", BH)
                    .has("source_address", sourceAddress)
                    .toList();
            }

            List<Vertex> deposits = initOutEdges.stream()
                .map(edge -> edge.inVertex())
                .distinct()
                .collect(Collectors.toList());

            for (Vertex deposit : deposits) {

                // Check whether deposit belongs to an exchange
                String depositAddr = (String) deposit.value("bulkLoader.vertex.id");
                if (depositAddr == null || exchangeAddresses.contains(depositAddr.toLowerCase())) {
                    continue;
                }

                List<Edge> inEdges;
                if (sourceAddress.equals("None")) {
                    inEdges = g.V(deposit).inE().toList().stream()
                        .filter(edge -> !"TT".equals(edge.value("behaviour2")) && 
                               !new BigInteger(edge.value("value").toString()).equals(BigInteger.ZERO))
                        .collect(Collectors.toList());
                } else {
                    inEdges = g.V(deposit).inE()
                        .has("behaviour2", BH)
                        .has("source_address", sourceAddress)
                        .toList();
                }

                List<Edge> outEdges;
                if (sourceAddress.equals("None")) {
                    outEdges = g.V(deposit).outE().toList().stream()
                        .filter(edge -> !"TT".equals(edge.value("behaviour2")) && 
                               !new BigInteger(edge.value("value").toString()).equals(BigInteger.ZERO))
                        .collect(Collectors.toList());
                } else {
                    outEdges = g.V(deposit).outE()
                        .has("behaviour2", BH)
                        .has("source_address", sourceAddress)
                        .toList();
                }

                for (Edge inEdge : inEdges) {
                    for (Edge outEdge : outEdges) {
                        int blockIn = Integer.parseInt(inEdge.value("block_number").toString());
                        int blockOut = Integer.parseInt(outEdge.value("block_number").toString());
                        BigInteger valueIn = new BigInteger(inEdge.value("value").toString());
                        BigInteger valueOut = new BigInteger(outEdge.value("value").toString());
                        BigInteger valueDiff = valueIn.subtract(valueOut);

                        final BigInteger ETH_THRESHOLD = new BigInteger("10000000000000000");

                        if ((blockIn - blockOut) < 3200 && valueDiff.compareTo(ETH_THRESHOLD) <= 0) {

                            Vertex inNode = inEdge.outVertex();
                            Vertex outNode = outEdge.inVertex();

                            // Check whether inNode belongs to exchange or miner
                            String inNodeAddr = (String) inNode.value("bulkLoader.vertex.id");
                            if (inNodeAddr == null || 
                                exchangeAddresses.contains(inNodeAddr.toLowerCase()) ||
                                minerAddresses.contains(inNodeAddr.toLowerCase())) {
                                continue;
                            }

                            // Check whether outNode belongs to exchange
                            String outNodeAddr = (String) outNode.value("bulkLoader.vertex.id");
                            if (outNodeAddr == null || !exchangeAddresses.contains(outNodeAddr.toLowerCase())) {
                                continue;
                            }

                            Set<Vertex> group = new LinkedHashSet<>();
                            group.add(inNode);
                            group.add(deposit);
                            matchedGroups.add(group);
                        }
                    }
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return matchedGroups;
    }

    // Format and print all groups
    private static void printAllGroups() {
        System.out.println("\nFound " + matchedGroups.size() + " matching groups:");
        matchedGroups.forEach(group -> {
            String nodeIds = group.stream()
                .map(v -> v.values("bulkLoader.vertex.id").next().toString())
                .sorted()
                .collect(Collectors.joining(", "));
            System.out.println(nodeIds);
        });
    }

    // Find weakly connected component based on group structure in matchedGroups
    private static Set<Vertex> findWeaklyConnectedComponent(Vertex initVertex, Set<Set<Vertex>> matchedGroups) {
        Map<Vertex, Set<Vertex>> adjacencyList = new HashMap<>();
        Set<Vertex> allNodes = new HashSet<>();

        // Build adjacency list
        for (Set<Vertex> group : matchedGroups) {
            List<Vertex> nodes = new ArrayList<>(group);
            allNodes.addAll(nodes);

            // Fully connect nodes within each group
            for (int i = 0; i < nodes.size(); i++) {
                Vertex node1 = nodes.get(i);
                for (int j = i + 1; j < nodes.size(); j++) {
                    Vertex node2 = nodes.get(j);
                    adjacencyList.computeIfAbsent(node1, k -> new HashSet<>()).add(node2);
                    adjacencyList.computeIfAbsent(node2, k -> new HashSet<>()).add(node1);
                }
            }
        }

        // If initVertex is not in the node set, return empty set
        if (!allNodes.contains(initVertex)) {
            return Collections.emptySet();
        }

        // BFS traversal
        Set<Vertex> visited = new HashSet<>();
        Queue<Vertex> queue = new LinkedList<>();
        queue.add(initVertex);
        visited.add(initVertex);

        while (!queue.isEmpty()) {
            Vertex current = queue.poll();
            for (Vertex neighbor : adjacencyList.getOrDefault(current, Collections.emptySet())) {
                if (!visited.contains(neighbor)) {
                    visited.add(neighbor);
                    queue.add(neighbor);
                }
            }
        }

        return visited;
    }

    // Write result to file
    private static void writeWCCToFile(Set<Vertex> wcc, String filename) {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(filename))) {
            for (Vertex v : wcc) {
                String address = (String) v.value("bulkLoader.vertex.id");
                writer.write(address + "\n");
            }
            System.out.println("Weakly connected component written to file: " + filename);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
