package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import java.math.BigInteger;
import java.util.*;
import java.util.stream.Collectors;

public class SG2_dec {

    // Store all matched address groups
    private static List<Set<Vertex>> matchedGroups = new ArrayList<>();

    // Dynamic threshold parameter
    private static BigInteger dynamicThreshold = new BigInteger("10");


    public static List<Set<Vertex>> processMidAddress(String address,
                                                      GraphTraversalSource g,
                                                      String BH,
                                                      String source_address,
                                                      boolean strict) {

        try {

            // Query the given middle address
            Vertex MidAdd = g.V().has("bulkLoader.vertex.id", address).next();

            // Step 1: Retrieve in/out edges satisfying time and value conditions
            List<Edge> allEdges = new ArrayList<>();

            if (source_address.equals("None")) {

                allEdges = g.V(MidAdd).bothE()
                        .toList()
                        .stream()
                        .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                        .collect(Collectors.toList());

            } else {

                g.V(MidAdd).bothE()
                        .has("behaviour2", BH)
                        .has("source_address", source_address)
                        .forEachRemaining(allEdges::add);
            }

            // Remove zero-value edges and sort by block number
            allEdges = allEdges.stream()
                    .filter(e -> !new BigInteger(e.value("value").toString())
                            .equals(BigInteger.ZERO))
                    .sorted(Comparator.comparing(
                            e -> new BigInteger(
                                    e.value("block_number").toString())))
                    .collect(Collectors.toList());

            // Traverse adjacent edge pairs
            for (int i = 0; i < allEdges.size() - 1; i++) {

                Edge e1 = allEdges.get(i);
                Edge e2 = allEdges.get(i + 1);

                boolean e1In = e1.inVertex().equals(MidAdd);
                boolean e2Out = e2.outVertex().equals(MidAdd);

                // Time adjacency condition
                if (e1In && e2Out) {

                    BigInteger inValue =
                            new BigInteger(e1.value("value").toString());
                    BigInteger outValue =
                            new BigInteger(e2.value("value").toString());

                    // Value difference condition
                    BigInteger diff = inValue.subtract(outValue);
                    BigInteger minVal = inValue.min(outValue);

                    if (minVal.compareTo(diff.multiply(dynamicThreshold)) >= 0
                            && diff.compareTo(BigInteger.ZERO) >= 0) {

                        Vertex inSource = e1.outVertex();
                        Vertex outTarget = e2.inVertex();

                        // Step 2: Find intersection of neighbors
                        List<Vertex> inSourceOuts;
                        List<Vertex> outTargetIns;

                        if (source_address.equals("None")) {

                            inSourceOuts = g.V(inSource).outE()
                                    .toList()
                                    .stream()
                                    .filter(edge ->
                                            !"TT".equals(edge.value("behaviour2")))
                                    .map(Edge::inVertex)
                                    .distinct()
                                    .collect(Collectors.toList());

                            outTargetIns = g.V(outTarget).inE()
                                    .toList()
                                    .stream()
                                    .filter(edge ->
                                            !"TT".equals(edge.value("behaviour2")))
                                    .map(Edge::outVertex)
                                    .distinct()
                                    .collect(Collectors.toList());

                        } else {

                            inSourceOuts = g.V(inSource)
                                    .outE()
                                    .has("behaviour2", BH)
                                    .has("source_address", source_address)
                                    .inV()
                                    .dedup()
                                    .toList();

                            outTargetIns = g.V(outTarget)
                                    .inE()
                                    .has("behaviour2", BH)
                                    .has("source_address", source_address)
                                    .outV()
                                    .dedup()
                                    .toList();
                        }

                        inSourceOuts.retainAll(outTargetIns);

                        // Step 3: Deep validation for each intersected vertex
                        for (Vertex a : inSourceOuts) {

                            if (!a.equals(MidAdd)) {

                                List<Edge> other_allEdges = new ArrayList<>();

                                if (source_address.equals("None")) {

                                    other_allEdges = g.V(a).bothE()
                                            .toList()
                                            .stream()
                                            .filter(edge ->
                                                    !"TT".equals(edge.value("behaviour2")))
                                            .collect(Collectors.toList());

                                } else {

                                    g.V(a).bothE()
                                            .has("behaviour2", BH)
                                            .has("source_address", source_address)
                                            .forEachRemaining(other_allEdges::add);
                                }

                                other_allEdges = other_allEdges.stream()
                                        .filter(e -> !new BigInteger(
                                                e.value("value").toString())
                                                .equals(BigInteger.ZERO))
                                        .sorted(Comparator.comparing(
                                                e -> new BigInteger(
                                                        e.value("block_number")
                                                                .toString())))
                                        .collect(Collectors.toList());

                                for (int j = 0;
                                     j < other_allEdges.size() - 1;
                                     j++) {

                                    Edge other_e1 = other_allEdges.get(j);
                                    Edge other_e2 =
                                            other_allEdges.get(j + 1);

                                    boolean other_e1In =
                                            other_e1.inVertex().equals(a);
                                    boolean other_e2Out =
                                            other_e2.outVertex().equals(a);
                                    boolean other_e1Out =
                                            other_e1.outVertex()
                                                    .equals(inSource);
                                    boolean other_e2In =
                                            other_e2.inVertex()
                                                    .equals(outTarget);

                                    if (other_e1In && other_e2Out
                                            && other_e1Out && other_e2In) {

                                        BigInteger other_invalue =
                                                new BigInteger(
                                                        other_e1.value("value")
                                                                .toString());

                                        BigInteger other_outvalue =
                                                new BigInteger(
                                                        other_e2.value("value")
                                                                .toString());

                                        BigInteger other_diff =
                                                other_invalue.subtract(
                                                        other_outvalue);

                                        BigInteger other_minVal =
                                                other_invalue.min(
                                                        other_outvalue);

                                        if (other_minVal.compareTo(
                                                other_diff.multiply(
                                                        dynamicThreshold))
                                                >= 0
                                                && other_diff.compareTo(
                                                BigInteger.ZERO) >= 0) {

                                            Set<Vertex> newGroup =
                                                    new HashSet<>();

                                            if (strict) {

                                                newGroup.add(a);
                                                newGroup.add(MidAdd);

                                            } else {

                                                newGroup.add(a);
                                                newGroup.add(MidAdd);
                                                newGroup.add(outTarget);
                                            }

                                            addGroup(newGroup);
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            System.out.println("Finished processing middle address.\n");
            printAllGroups();

        } catch (Exception e) {
            e.printStackTrace();
        }

        return matchedGroups;
    }


    public static List<Set<Vertex>> processRecAddress(String address,
                                                      GraphTraversalSource g,
                                                      String BH,
                                                      String source_address,
                                                      boolean strict) {

        try {

            Vertex RecAdd =
                    g.V().has("bulkLoader.vertex.id", address).next();

            // Step 1: Retrieve predecessor nodes
            List<Vertex> MidV_list;

            if (source_address.equals("None")) {

                MidV_list = g.V(RecAdd).inE()
                        .toList()
                        .stream()
                        .filter(edge ->
                                !"TT".equals(edge.value("behaviour2")))
                        .map(Edge::outVertex)
                        .distinct()
                        .collect(Collectors.toList());

            } else {

                MidV_list = g.V(RecAdd)
                        .inE()
                        .has("behaviour2", BH)
                        .has("source_address", source_address)
                        .outV()
                        .dedup()
                        .toList();
            }

            for (int i = 0; i < MidV_list.size() - 1; i++) {

                Vertex MidV = MidV_list.get(i);

                List<Edge> allEdges = new ArrayList<>();

                if (source_address.equals("None")) {

                    allEdges = g.V(MidV).bothE()
                            .toList()
                            .stream()
                            .filter(edge ->
                                    !"TT".equals(edge.value("behaviour2")))
                            .collect(Collectors.toList());

                } else {

                    g.V(MidV).bothE()
                            .has("behaviour2", BH)
                            .has("source_address", source_address)
                            .forEachRemaining(allEdges::add);
                }

                allEdges = allEdges.stream()
                        .filter(e ->
                                !new BigInteger(
                                        e.value("value").toString())
                                        .equals(BigInteger.ZERO))
                        .sorted(Comparator.comparing(
                                e -> new BigInteger(
                                        e.value("block_number")
                                                .toString())))
                        .collect(Collectors.toList());

                for (int j = 0;
                     j < allEdges.size() - 1;
                     j++) {

                    Edge e1 = allEdges.get(j);
                    Edge e2 = allEdges.get(j + 1);

                    boolean e1In =
                            e1.inVertex().equals(MidV);
                    boolean e2Out =
                            e2.outVertex().equals(MidV);
                    boolean e2In =
                            e2.inVertex().equals(RecAdd);

                    if (e1In && e2Out && e2In) {

                        BigInteger inValue =
                                new BigInteger(
                                        e1.value("value").toString());

                        BigInteger outValue =
                                new BigInteger(
                                        e2.value("value").toString());

                        BigInteger diff =
                                inValue.subtract(outValue);

                        BigInteger minVal =
                                inValue.min(outValue);

                        if (minVal.compareTo(
                                diff.multiply(dynamicThreshold)) >= 0
                                && diff.compareTo(
                                BigInteger.ZERO) >= 0) {

                            Vertex outTarget =
                                    e2.inVertex();

                            Set<Vertex> group =
                                    new HashSet<>();

                            group.add(MidV);
                            group.add(outTarget);

                            addGroup(group);
                        }
                    }
                }
            }

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


    // Helper method (kept for structural completeness)
    private static boolean isClose(BigInteger a,
                                   BigInteger b,
                                   BigInteger threshold) {

        return a.subtract(b)
                .abs()
                .compareTo(threshold) <= 0;
    }
}
