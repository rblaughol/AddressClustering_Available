package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;
import java.math.BigInteger;
import java.util.*;
import java.util.stream.Collectors;

public class SG1_dec {

    // Store all matched address groups
    private static List<Set<Vertex>> matchedGroups = new ArrayList<>();

    // Dynamic threshold parameter
    private static BigInteger dynamicThreshold = new BigInteger("10");


    public static List<Set<Vertex>> processInitAddress(String address,
                                                       GraphTraversalSource g,
                                                       String BH,
                                                       String source_address,
                                                       boolean strict) {

        try {

            // Locate the given initial address
            Vertex init_v = g.V().has("bulkLoader.vertex.id", address).next();

            // Query outgoing transactions and corresponding deposit nodes
            List<Vertex> deposits;

            if (source_address.equals("None")) {

                deposits = g.V(init_v).outE()
                        .toList()
                        .stream()
                        .filter(edge ->
                                (!"TT".equals(edge.value("behaviour2"))
                                        && (!new BigInteger(edge.value("value").toString())
                                        .equals(BigInteger.ZERO))))
                        .map(Edge::inVertex)
                        .distinct()
                        .collect(Collectors.toList());

            } else {

                deposits = g.V(init_v)
                        .outE()
                        .has("behaviour2", BH)
                        .has("source_address", source_address)
                        .inV()
                        .dedup()
                        .toList();
            }

            for (Vertex deposit : deposits) {

                // Pre-build block number mapping: record all incoming transactions
                TreeMap<BigInteger, List<Edge>> blockMap = new TreeMap<>();

                List<Edge> inEdges;

                if (source_address.equals("None")) {

                    inEdges = g.V(deposit).inE().toList()
                            .stream()
                            .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                            .collect(Collectors.toList());

                } else {

                    inEdges = g.V(deposit)
                            .inE()
                            .has("behaviour2", BH)
                            .has("source_address", source_address)
                            .toList();
                }

                for (Edge inEdge : inEdges) {

                    if (!new BigInteger(inEdge.value("value").toString())
                            .equals(BigInteger.ZERO)) {

                        BigInteger blockNum =
                                new BigInteger(inEdge.value("block_number").toString());

                        blockMap.computeIfAbsent(blockNum,
                                k -> new ArrayList<>()).add(inEdge);
                    }
                }

                BigInteger balance = BigInteger.ZERO;

                // Query outgoing transactions and construct subgraphs
                List<Edge> sortedOutEdges;

                if (source_address.equals("None")) {

                    sortedOutEdges = g.V(deposit).outE().toList()
                            .stream()
                            .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                            .collect(Collectors.toList());

                } else {

                    sortedOutEdges = g.V(deposit)
                            .outE()
                            .has("behaviour2", BH)
                            .has("source_address", source_address)
                            .toList();
                }

                sortedOutEdges = sortedOutEdges.stream()
                        .filter(e -> !new BigInteger(e.value("value").toString())
                                .equals(BigInteger.ZERO))
                        .sorted(Comparator.comparing(
                                e -> new BigInteger(
                                        e.value("block_number").toString())))
                        .collect(Collectors.toList());

                BigInteger lowerBound = BigInteger.ZERO;

                // Traverse outgoing transactions
                for (Edge outEdge : sortedOutEdges) {

                    final BigInteger currentUpper =
                            new BigInteger(outEdge.value("block_number").toString());

                    // Efficient range query for incoming edges
                    Map<BigInteger, List<Edge>> subMap =
                            blockMap.subMap(lowerBound, true,
                                    currentUpper, false);

                    lowerBound = currentUpper;

                    List<Edge> relevantInEdges = subMap.values()
                            .stream()
                            .flatMap(List::stream)
                            .collect(Collectors.toList());

                    // Calculate incoming amount
                    Set<Vertex> inNodes = new HashSet<>();

                    BigInteger sumIn = relevantInEdges.stream()
                            .map(e -> {
                                BigInteger val =
                                        new BigInteger(e.value("value").toString());
                                inNodes.add(e.outVertex());
                                return val;
                            })
                            .reduce(BigInteger.ZERO, BigInteger::add);

                    // Update balance
                    BigInteger outValue =
                            new BigInteger(outEdge.value("value").toString());

                    BigInteger balanceBefore = balance;

                    balance = balanceBefore.add(sumIn).subtract(outValue);

                    if (balance.compareTo(BigInteger.ZERO) < 0) {
                        balance = BigInteger.ZERO;
                    }

                    // Only perform deanonymization if init node is included
                    boolean containsInitNode = inNodes.stream()
                            .anyMatch(v -> v.id().equals(init_v.id()));

                    if (containsInitNode) {

                        if (strict) {

                            // Condition 1: sumIn ≈ outValue
                            if (isClose(relevantInEdges, sumIn,
                                    outValue, dynamicThreshold)) {

                                if (inNodes.size() >= 2) {
                                    addGroup(new HashSet<>(inNodes));
                                }
                            }

                            // Condition 2: balanceBefore + sumIn ≈ outValue
                            if (isClose(relevantInEdges,
                                    sumIn.add(balanceBefore),
                                    outValue, dynamicThreshold)) {

                                Set<Vertex> comboGroup =
                                        new HashSet<>(inNodes);

                                if (comboGroup.size() >= 2) {
                                    addGroup(comboGroup);
                                }
                            }

                        } else {

                            if (isClose(relevantInEdges,
                                    sumIn, outValue, dynamicThreshold)) {

                                inNodes.add(deposit);

                                if (inNodes.size() >= 2) {
                                    addGroup(inNodes);
                                }
                            }

                            if (isClose(relevantInEdges,
                                    sumIn.add(balanceBefore),
                                    outValue, dynamicThreshold)) {

                                inNodes.add(deposit);

                                if (inNodes.size() >= 2) {
                                    addGroup(inNodes);
                                }
                            }
                        }
                    }
                }
            }

            System.out.println("Finished processing initial address.\n");
            printAllGroups();

        } catch (Exception e) {
            e.printStackTrace();
        }

        return matchedGroups;
    }


    public static List<Set<Vertex>> processDepositAddress(String address,
                                                          GraphTraversalSource g,
                                                          String BH,
                                                          String source_address,
                                                          boolean strict) {

        try {

            Vertex deposit =
                    g.V().has("bulkLoader.vertex.id", address).next();

            // Pre-build block number mapping for incoming transactions
            TreeMap<BigInteger, List<Edge>> blockMap =
                    new TreeMap<>();

            List<Edge> inEdges;

            if (source_address.equals("None")) {

                inEdges = g.V(deposit).inE().toList()
                        .stream()
                        .filter(edge ->
                                !"TT".equals(edge.value("behaviour2")))
                        .collect(Collectors.toList());

            } else {

                inEdges = g.V(deposit)
                        .inE()
                        .has("behaviour2", BH)
                        .has("source_address", source_address)
                        .toList();
            }

            for (Edge inEdge : inEdges) {

                if (!new BigInteger(inEdge.value("value").toString())
                        .equals(BigInteger.ZERO)) {

                    BigInteger blockNum =
                            new BigInteger(inEdge.value("block_number").toString());

                    blockMap.computeIfAbsent(blockNum,
                            k -> new ArrayList<>()).add(inEdge);
                }
            }

            BigInteger balance = BigInteger.ZERO;

            List<Edge> sortedOutEdges;

            if (source_address.equals("None")) {

                sortedOutEdges = g.V(deposit).outE().toList()
                        .stream()
                        .filter(edge ->
                                !"TT".equals(edge.value("behaviour2")))
                        .collect(Collectors.toList());

            } else {

                sortedOutEdges = g.V(deposit)
                        .outE()
                        .has("behaviour2", BH)
                        .has("source_address", source_address)
                        .toList();
            }

            sortedOutEdges = sortedOutEdges.stream()
                    .filter(e ->
                            !new BigInteger(e.value("value").toString())
                                    .equals(BigInteger.ZERO))
                    .sorted(Comparator.comparing(
                            e -> new BigInteger(
                                    e.value("block_number").toString())))
                    .collect(Collectors.toList());

            BigInteger lowerBound = BigInteger.ZERO;

            for (Edge outEdge : sortedOutEdges) {

                final BigInteger currentUpper =
                        new BigInteger(outEdge.value("block_number").toString());

                Map<BigInteger, List<Edge>> subMap =
                        blockMap.subMap(lowerBound, true,
                                currentUpper, false);

                lowerBound = currentUpper;

                List<Edge> relevantInEdges =
                        subMap.values().stream()
                                .flatMap(List::stream)
                                .collect(Collectors.toList());

                Set<Vertex> inNodes = new HashSet<>();

                BigInteger sumIn = relevantInEdges.stream()
                        .map(e -> {
                            BigInteger val =
                                    new BigInteger(e.value("value").toString());
                            inNodes.add(e.outVertex());
                            return val;
                        })
                        .reduce(BigInteger.ZERO, BigInteger::add);

                BigInteger outValue =
                        new BigInteger(outEdge.value("value").toString());

                BigInteger balanceBefore = balance;

                balance = balanceBefore.add(sumIn)
                        .subtract(outValue);

                if (balance.compareTo(BigInteger.ZERO) < 0) {
                    balance = BigInteger.ZERO;
                }

                // Only Condition 2 is applied here
                if (isClose(relevantInEdges,
                        sumIn.add(balanceBefore),
                        outValue,
                        dynamicThreshold)) {

                    Set<Vertex> comboGroup =
                            new HashSet<>(inNodes);

                    comboGroup.add(deposit);

                    if (comboGroup.size() >= 2) {
                        addGroup(comboGroup);
                    }
                }
            }

            System.out.println("Finished processing deposit address.\n");
            printAllGroups();

        } catch (Exception e) {
            e.printStackTrace();
        }

        return matchedGroups;
    }


    // Add group with deduplication
    private static synchronized void addGroup(Set<Vertex> newGroup) {

        Set<Object> newIds = newGroup.stream()
                .map(Vertex::id)
                .collect(Collectors.toSet());

        boolean exists = matchedGroups.stream()
                .anyMatch(existing ->
                        existing.stream()
                                .map(Vertex::id)
                                .collect(Collectors.toSet())
                                .equals(newIds));

        if (!exists) {
            matchedGroups.add(newGroup);
        }
    }


    // Print all matched groups
    private static void printAllGroups() {

        System.out.println("\nDetected "
                + matchedGroups.size()
                + " matched groups:");

        matchedGroups.forEach(group -> {

            String nodeIds = group.stream()
                    .map(v -> v.id().toString())
                    .sorted()
                    .collect(Collectors.joining(", "));
        });
    }


    private static boolean isClose(List<Edge> edges,
                                   BigInteger sumIn,
                                   BigInteger outValue,
                                   BigInteger threshold) {

        // Find maximum non-zero edge value
        BigInteger minNonZeroValue = edges.stream()
                .map(e -> new BigInteger(e.value("value").toString()))
                .filter(v -> !v.equals(BigInteger.ZERO))
                .max(BigInteger::compareTo)
                .orElse(BigInteger.ZERO);

        if (minNonZeroValue.compareTo(BigInteger.ZERO) <= 0) {
            return false;
        }

        BigInteger difference =
                sumIn.subtract(outValue);

        BigInteger mul_difference =
                difference.multiply(threshold);

        return minNonZeroValue.compareTo(mul_difference) >= 0;
    }
}
