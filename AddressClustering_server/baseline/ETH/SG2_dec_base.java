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

public class SG2_dec_base {
    private static List<Set<Vertex>> matchedGroups = new ArrayList<>();
    private static BigInteger dynamicThreshold = new BigInteger("10");

    public static void main(String[] args) {
        JanusGraph graph = JanusGraphFactory.open(
            "/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();
        
        List<String> addresses = readAddressesFromFile("Tokenadd.txt");
        String outputDir = "Tokenadd_sg2/";
        new File(outputDir).mkdirs();

        for (String clusterAdd : addresses) {
            List<Set<Vertex>> allMatchedGroups = new ArrayList<>();
            boolean strict = true;

            // Process mid-level address
            matchedGroups.clear();
            List<Set<Vertex>> midGroups = processMidAddress(clusterAdd, g, "None", "None", strict);
            allMatchedGroups.addAll(midGroups);

            // Process DV addresses
            List<Object> DVs = g.V().has("bulkLoader.vertex.id", clusterAdd)
                    .bothE().values("source_address").toList();
            List<Object> uniqueDVs = DVs.stream().distinct().collect(Collectors.toList());
            for (Object dvObj : uniqueDVs) {
                String DV = dvObj.toString();
                matchedGroups.clear();
                List<Set<Vertex>> dvGroups = processMidAddress(clusterAdd, g, "TT", DV, strict);
                allMatchedGroups.addAll(dvGroups);
            }

            // Write matched groups to file
            writeGroupsToFile(allMatchedGroups, outputDir + clusterAdd + ".out");
        }

        graph.close();
    }

    private static List<String> readAddressesFromFile(String filename) {
        List<String> addresses = new ArrayList<>();
        try (Scanner scanner = new Scanner(new File(filename))) {
            while (scanner.hasNextLine()) {
                String line = scanner.nextLine().trim();
                if (!line.isEmpty()) addresses.add(line);
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

    public static List<Set<Vertex>> processMidAddress(String address, GraphTraversalSource g, String BH, String sourceAddress, boolean strict) {
        try {
            // Get the mid-level vertex
            Vertex midVertex = g.V().has("bulkLoader.vertex.id", address).next();

            // Fetch all relevant edges
            List<Edge> allEdges;
            if ("None".equals(sourceAddress)) {
                allEdges = g.V(midVertex).bothE().toList().stream()
                        .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                        .collect(Collectors.toList());
            } else {
                allEdges = new ArrayList<>();
                g.V(midVertex).bothE().has("behaviour2", BH)
                        .has("source_address", sourceAddress)
                        .forEachRemaining(allEdges::add);
            }

            // Filter non-zero values and sort by block number
            allEdges = allEdges.stream()
                    .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                    .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                    .collect(Collectors.toList());

            // Traverse edges to find potential matching groups
            for (int i = 0; i < allEdges.size() - 1; i++) {
                Edge e1 = allEdges.get(i);
                Edge e2 = allEdges.get(i + 1);

                boolean e1In = e1.inVertex().equals(midVertex);
                boolean e2Out = e2.outVertex().equals(midVertex);

                if (e1In && e2Out) {
                    BigInteger inValue = new BigInteger(e1.value("value").toString());
                    BigInteger outValue = new BigInteger(e2.value("value").toString());
                    BigInteger diff = inValue.subtract(outValue);
                    BigInteger minVal = inValue.min(outValue);

                    if (minVal.compareTo(diff.multiply(dynamicThreshold)) >= 0 && diff.compareTo(BigInteger.ZERO) >= 0) {
                        Vertex inSource = e1.outVertex();
                        Vertex outTarget = e2.inVertex();

                        // Find intersection of out-neighbors of inSource and in-neighbors of outTarget
                        List<Vertex> inSourceOuts = getNeighbors(inSource, g, BH, sourceAddress, true);
                        List<Vertex> outTargetIns = getNeighbors(outTarget, g, BH, sourceAddress, false);

                        inSourceOuts.retainAll(outTargetIns);

                        for (Vertex candidate : inSourceOuts) {
                            if (!candidate.equals(midVertex)) {
                                Set<Vertex> newGroup = new HashSet<>();
                                if (strict) {
                                    newGroup.add(candidate);
                                    newGroup.add(midVertex);
                                } else {
                                    newGroup.add(candidate);
                                    newGroup.add(midVertex);
                                    newGroup.add(outTarget);
                                }
                                addGroup(newGroup);
                            }
                        }
                    }
                }
            }

            System.out.println("Finished processing mid-level address: " + address);
            printAllGroups();

        } catch (Exception e) {
            e.printStackTrace();
        }
        return matchedGroups;
    }

    private static List<Vertex> getNeighbors(Vertex v, GraphTraversalSource g, String BH, String sourceAddress, boolean out) {
        List<Vertex> neighbors;
        if ("None".equals(sourceAddress)) {
            neighbors = out ? g.V(v).outE().toList() : g.V(v).inE().toList();
            neighbors = neighbors.stream()
                    .filter(e -> !"TT".equals(e.value("behaviour2")))
                    .map(e -> out ? e.inVertex() : e.outVertex())
                    .distinct()
                    .collect(Collectors.toList());
        } else {
            neighbors = out ? g.V(v).outE().has("behaviour2", BH).has("source_address", sourceAddress).inV().dedup().toList()
                            : g.V(v).inE().has("behaviour2", BH).has("source_address", sourceAddress).outV().dedup().toList();
        }
        return neighbors;
    }

    private static synchronized void addGroup(Set<Vertex> newGroup) {
        Set<Object> newIds = newGroup.stream().map(Vertex::id).collect(Collectors.toSet());
        boolean exists = matchedGroups.stream()
                .anyMatch(existing -> existing.stream().map(Vertex::id).collect(Collectors.toSet()).equals(newIds));
        if (!exists) matchedGroups.add(newGroup);
    }

    private static void printAllGroups() {
        System.out.println("\nFound " + matchedGroups.size() + " matched groups.");
    }

    private static boolean isClose(BigInteger a, BigInteger b, BigInteger threshold) {
        return a.subtract(b).abs().compareTo(threshold) <= 0;
    }
}
