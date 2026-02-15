package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;

import java.io.*;
import java.math.BigInteger;
import java.util.*;
import java.util.stream.Collectors;

public class SG1_dec_base {
    private static List<Set<Vertex>> matchedGroups = new ArrayList<>();
    private static BigInteger dynamicThreshold = new BigInteger("10");

    public static void main(String[] args) {
        JanusGraph graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();
        
        List<String> addresses = readAddressesFromFile("Tokenadd.txt");
        String outputDir = "Tokenadd_sg1/";
        new File(outputDir).mkdirs();

        for (String clusterAdd : addresses) {
            List<Set<Vertex>> allMatchedGroups = new ArrayList<>();
            boolean strict = true;

            // Process initial address
            matchedGroups.clear();
            List<Set<Vertex>> initGroups = processInitAddress(clusterAdd, g, "None", "None", strict);
            allMatchedGroups.addAll(initGroups);

            // Process DV addresses
            List<Object> DVs = g.V().has("bulkLoader.vertex.id", clusterAdd).bothE().values("source_address").toList();
            List<Object> uniqueDVs = DVs.stream().distinct().collect(Collectors.toList());
            for (Object dvObj : uniqueDVs) {
                String DV = dvObj.toString();
                matchedGroups.clear();
                List<Set<Vertex>> dvGroups = processInitAddress(clusterAdd, g, "TT", DV, strict);
                allMatchedGroups.addAll(dvGroups);
            }

            // Write results to file
            writeGroupsToFile(allMatchedGroups, outputDir + clusterAdd + ".out");
        }
        
        graph.close();
    }

    private static List<String> readAddressesFromFile(String filename) {
        List<String> addresses = new ArrayList<>();
        try (Scanner scanner = new Scanner(new File(filename))) {
            while (scanner.hasNextLine()) {
                String line = scanner.nextLine().trim();
                if (!line.isEmpty()) {
                    addresses.add(line);
                }
            }
        } catch (FileNotFoundException e) {
            e.printStackTrace();
        }
        return addresses;
    }

    private static void writeGroupsToFile(List<Set<Vertex>> groups, String filename) {
        try (PrintWriter writer = new PrintWriter(new FileWriter(filename))) {
            for (Set<Vertex> group : groups) {
                String line = group.stream()
                    .map(v -> v.id().toString())
                    .sorted()
                    .collect(Collectors.joining(", "));
                writer.println("[" + line + "]");
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public static List<Set<Vertex>> processInitAddress(String address, GraphTraversalSource g, String BH, String source_address, boolean strict) {
        try {
            // Find the initial vertex
            Vertex init_v = g.V().has("bulkLoader.vertex.id", address).next();

            // Get outgoing deposit vertices
            List<Vertex> deposits;
            if (source_address.equals("None")) {
                deposits = g.V(init_v).outE()
                        .toList()
                        .stream()
                        .filter(edge -> (!"TT".equals(edge.value("behaviour2")) &&
                                         (!new BigInteger(edge.value("value").toString()).equals(BigInteger.ZERO))))
                        .map(Edge::inVertex)
                        .distinct()
                        .collect(Collectors.toList());
            } else {
                deposits = g.V(init_v).outE().has("behaviour2", BH).has("source_address", source_address).inV().dedup().toList();
            }

            for (Vertex deposit : deposits) {
                // Pre-build a mapping of block numbers to incoming edges
                TreeMap<BigInteger, List<Edge>> blockMap = new TreeMap<>();
                List<Edge> inEdges;
                if (source_address.equals("None")){
                    inEdges = g.V(deposit).inE().toList().stream()
                            .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                            .collect(Collectors.toList());
                } else {
                    inEdges = g.V(deposit).inE().has("behaviour2", BH).has("source_address", source_address).toList();
                }
                for (Edge inEdge : inEdges) {
                    if (!new BigInteger(inEdge.value("value").toString()).equals(BigInteger.ZERO)) {
                        BigInteger blockNum = new BigInteger(inEdge.value("block_number").toString());
                        blockMap.computeIfAbsent(blockNum, k -> new ArrayList<>()).add(inEdge);
                    }
                }

                BigInteger balance = BigInteger.ZERO;

                // Process outgoing edges
                List<Edge> sortedOutEdges;
                if (source_address.equals("None")) {
                    sortedOutEdges = g.V(deposit).outE().toList().stream()
                            .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                            .collect(Collectors.toList());
                } else {
                    sortedOutEdges = g.V(deposit).outE().has("behaviour2", BH).has("source_address", source_address).toList();
                }

                sortedOutEdges = sortedOutEdges.stream()
                        .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                        .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                        .collect(Collectors.toList());

                BigInteger lowerBound = BigInteger.ZERO;

                for (Edge outEdge : sortedOutEdges) {
                    final BigInteger currentUpper = new BigInteger(outEdge.value("block_number").toString());
                    Map<BigInteger, List<Edge>> subMap = blockMap.subMap(lowerBound, true, currentUpper, false);
                    lowerBound = currentUpper;

                    List<Edge> relevantInEdges = subMap.values().stream().flatMap(List::stream).collect(Collectors.toList());

                    Set<Vertex> inNodes = new HashSet<>();
                    BigInteger sumIn = relevantInEdges.stream()
                            .map(e -> {
                                BigInteger val = new BigInteger(e.value("value").toString());
                                inNodes.add(e.outVertex());
                                return val;
                            })
                            .reduce(BigInteger.ZERO, BigInteger::add);

                    BigInteger outValue = new BigInteger(outEdge.value("value").toString());
                    BigInteger balanceBefore = balance;
                    balance = balanceBefore.add(sumIn).subtract(outValue);

                    if (balance.compareTo(BigInteger.ZERO) < 0) {
                        balance = BigInteger.ZERO;
                    }

                    boolean containsInitNode = inNodes.stream().anyMatch(v -> v.id().equals(init_v.id()));

                    if (containsInitNode) {
                        if (strict) {
                            if (isClose(relevantInEdges, sumIn, outValue, dynamicThreshold)) {
                                if (inNodes.size() >= 2) addGroup(new HashSet<>(inNodes));
                            }
                            if (isClose(relevantInEdges, sumIn.add(balanceBefore), outValue, dynamicThreshold)) {
                                Set<Vertex> comboGroup = new HashSet<>(inNodes);
                                if (comboGroup.size() >= 2) addGroup(comboGroup);
                            }
                        } else {
                            if (isClose(relevantInEdges, sumIn, outValue, dynamicThreshold)) {
                                inNodes.add(deposit);
                                if (inNodes.size() >= 2) addGroup(inNodes);
                            }
                            if (isClose(relevantInEdges, sumIn.add(balanceBefore), outValue, dynamicThreshold)) {
                                inNodes.add(deposit);
                                if (inNodes.size() >= 2) addGroup(inNodes);
                            }
                        }
                    }
                }
            }

            System.out.println("Finished processing initial address\n");
            printAllGroups();

        } catch (Exception e) { 
            e.printStackTrace();
        }
        return matchedGroups;
    }

    private static synchronized void addGroup(Set<Vertex> newGroup) {
        Set<Object> newIds = newGroup.stream().map(Vertex::id).collect(Collectors.toSet());
        boolean exists = matchedGroups.stream()
                .anyMatch(existing -> existing.stream().map(Vertex::id).collect(Collectors.toSet()).equals(newIds));
        if (!exists) matchedGroups.add(newGroup);
    }

    private static void printAllGroups() {
        System.out.println("\nFound " + matchedGroups.size() + " matched groups:");
        matchedGroups.forEach(group -> {
            String nodeIds = group.stream().map(v -> v.id().toString()).sorted().collect(Collectors.joining(", "));
        });
    }

    private static boolean isClose(List<Edge> edges, BigInteger sumIn, BigInteger outValue, BigInteger threshold) {
        BigInteger maxNonZero = edges.stream()
                .map(e -> new BigInteger(e.value("value").toString()))
                .filter(v -> !v.equals(BigInteger.ZERO))
                .max(BigInteger::compareTo)
                .orElse(BigInteger.ZERO);

        if (maxNonZero.compareTo(BigInteger.ZERO) <= 0) return false;

        BigInteger difference = sumIn.subtract(outValue);
        BigInteger mul_difference = difference.multiply(threshold);

        return maxNonZero.compareTo(mul_difference) >= 0;
    }
}
