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

public class airdrop {

    private static List<Set<Vertex>> matchedGroups = new ArrayList<>();
    private static BigInteger dynamicThreshold = new BigInteger("10");

    public static void main(String[] args) {

        JanusGraph graph = JanusGraphFactory.open(
                "/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties"
        );

        GraphTraversalSource g = graph.traversal();

        List<String> addresses = readAddressesFromFile("Tokenadd.txt");

        String outputDir = "Tokenadd_airdrop/";
        new File(outputDir).mkdirs();

        for (int i = 0; i < addresses.size(); i++) {

            String ClusterAdd = addresses.get(i);
            List<Set<Vertex>> allMatchedGroups = new ArrayList<>();
            boolean strict = true;

            // Process each distinct DV
            List<Object> DVs = g.V()
                    .has("bulkLoader.vertex.id", ClusterAdd)
                    .bothE()
                    .values("source_address")
                    .dedup()
                    .toList();

            for (Object dv : DVs) {

                String DV = dv.toString();
                matchedGroups.clear();

                // Process middle address pattern
                List<Set<Vertex>> midTT =
                        processMidAddress(ClusterAdd, g, "TT", DV, strict);

                // Process receiving address pattern
                List<Set<Vertex>> recTT =
                        processRecAddress(ClusterAdd, g, "TT", DV, strict);

                allMatchedGroups.addAll(midTT);
                allMatchedGroups.addAll(recTT);
            }

            // Write result file
            writeGroupsToFile(allMatchedGroups,
                    outputDir + ClusterAdd + ".out");
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


    private static void writeGroupsToFile(List<Set<Vertex>> groups,
                                          String filename) {

        try (PrintWriter writer =
                     new PrintWriter(new FileWriter(filename))) {

            groups.forEach(group -> {

                String line = group.stream()
                        .map(v -> v.id().toString())
                        .sorted()
                        .collect(Collectors.joining(", "));

                writer.println("[" + line + "]");
            });

        } catch (IOException e) {
            e.printStackTrace();
        }
    }


    public static List<Set<Vertex>> processMidAddress(String address,
                                                      GraphTraversalSource g,
                                                      String BH,
                                                      String source_address,
                                                      boolean strict) {

        try {

            // Query the given address vertex
            Vertex MidAdd =
                    g.V().has("bulkLoader.vertex.id", address).next();

            // Step 1:
            // Retrieve in/out edges satisfying time and value conditions

            List<Edge> allEdges = new ArrayList<>();

            g.V(MidAdd)
                    .bothE()
                    .has("behaviour2", BH)
                    .has("source_address", source_address)
                    .forEachRemaining(allEdges::add);

            // Filter zero-value edges and sort by block number
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

            // Traverse adjacent transaction edges
            for (int i = 0; i < allEdges.size() - 1; i++) {

                Edge e1 = allEdges.get(i);
                Edge e2 = allEdges.get(i + 1);

                boolean e1In =
                        e1.inVertex().equals(MidAdd);
                boolean e2Out =
                        e2.outVertex().equals(MidAdd);

                // Adjacent edge condition (time constraint)
                if (e1In && e2Out) {

                    BigInteger inValue =
                            new BigInteger(
                                    e1.value("value").toString());

                    BigInteger outValue =
                            new BigInteger(
                                    e2.value("value").toString());

                    // Value equality condition
                    if (inValue.equals(outValue)) {

                        Vertex inSource = e1.outVertex();
                        Vertex outTarget = e2.inVertex();

                        // Step 2:
                        // Find intersection-related nodes

                        List<Vertex> inSourceOuts =
                                g.V(inSource)
                                        .outE()
                                        .has("behaviour2", BH)
                                        .has("source_address",
                                                source_address)
                                        .toList()
                                        .stream()
                                        .filter(e ->
                                                !new BigInteger(
                                                        e.value("value")
                                                                .toString())
                                                        .equals(BigInteger.ZERO))
                                        .sorted(Comparator.comparing(
                                                e -> new BigInteger(
                                                        e.value("block_number")
                                                                .toString())))
                                        .map(Edge::inVertex)
                                        .distinct()
                                        .collect(Collectors.toList());

                        for (int idx = 0;
                             idx < inSourceOuts.size();
                             idx++) {

                            Vertex MidAdd2 =
                                    inSourceOuts.get(idx);

                            // Skip itself
                            if (MidAdd2.equals(MidAdd)) {
                                continue;
                            }

                            // Retrieve all related edges of MidAdd2
                            List<Edge> midEdges =
                                    g.V(MidAdd2)
                                            .bothE()
                                            .has("behaviour2", BH)
                                            .has("source_address",
                                                    source_address)
                                            .toList()
                                            .stream()
                                            .filter(e ->
                                                    !new BigInteger(
                                                            e.value("value")
                                                                    .toString())
                                                            .equals(BigInteger.ZERO))
                                            .sorted(Comparator.comparing(
                                                    e -> new BigInteger(
                                                            e.value("block_number")
                                                                    .toString())))
                                            .collect(Collectors.toList());

                            for (int j = 0;
                                 j < midEdges.size() - 1;
                                 j++) {

                                Edge prevEdge =
                                        midEdges.get(j);
                                Edge nextEdge =
                                        midEdges.get(j + 1);

                                boolean isIncoming =
                                        prevEdge.inVertex()
                                                .equals(MidAdd2)
                                                && prevEdge.outVertex()
                                                .equals(inSource);

                                boolean isOutgoing =
                                        nextEdge.outVertex()
                                                .equals(MidAdd2)
                                                && nextEdge.inVertex()
                                                .equals(outTarget);

                                if (isIncoming && isOutgoing) {

                                    BigInteger inVal =
                                            new BigInteger(
                                                    prevEdge.value("value")
                                                            .toString());

                                    BigInteger outVal =
                                            new BigInteger(
                                                    nextEdge.value("value")
                                                            .toString());

                                    if (inValue.equals(inVal)
                                            && inValue.equals(outVal)) {

                                        Set<Vertex> cluster =
                                                new HashSet<>();

                                        cluster.add(MidAdd);
                                        cluster.add(MidAdd2);

                                        if (!strict) {
                                            cluster.add(outTarget);
                                        }

                                        addGroup(cluster);
                                        break;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            System.out.println(
                    "Finished processing middle address.\n");

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
                    g.V().has("bulkLoader.vertex.id", address)
                            .next();

            // Step 1:
            // Retrieve predecessor nodes

            List<Vertex> MidV_list;

            if (source_address.equals("None")) {

                MidV_list = g.V(RecAdd)
                        .inE()
                        .toList()
                        .stream()
                        .filter(edge ->
                                !"TT".equals(
                                        edge.value("behaviour2")))
                        .map(edge -> edge.outVertex())
                        .distinct()
                        .collect(Collectors.toList());

            } else {

                MidV_list =
                        g.V(RecAdd)
                                .inE()
                                .has("behaviour2", BH)
                                .has("source_address",
                                        source_address)
                                .outV()
                                .dedup()
                                .toList();
            }

            for (int i = 0;
                 i < MidV_list.size() - 1;
                 i++) {

                Vertex MidV =
                        MidV_list.get(i);

                List<Edge> allEdges =
                        new ArrayList<>();

                if (source_address.equals("None")) {

                    allEdges =
                            g.V(MidV)
                                    .bothE()
                                    .toList()
                                    .stream()
                                    .filter(edge ->
                                            !"TT".equals(
                                                    edge.value("behaviour2")))
                                    .collect(Collectors.toList());

                } else {

                    g.V(MidV)
                            .bothE()
                            .has("behaviour2", BH)
                            .has("source_address",
                                    source_address)
                            .forEachRemaining(allEdges::add);
                }

                allEdges =
                        allEdges.stream()
                                .filter(e ->
                                        !new BigInteger(
                                                e.value("value")
                                                        .toString())
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
                                        e1.value("value")
                                                .toString());

                        BigInteger outValue =
                                new BigInteger(
                                        e2.value("value")
                                                .toString());

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

        Set<Object> newIds =
                newGroup.stream()
                        .map(Vertex::id)
                        .collect(Collectors.toSet());

        boolean exists =
                matchedGroups.stream()
                        .anyMatch(existing ->
                                existing.stream()
                                        .map(Vertex::id)
                                        .collect(Collectors.toSet())
                                        .equals(newIds));

        if (!exists) {
            matchedGroups.add(newGroup);
        }
    }


    // Print all detected groups
    private static void printAllGroups() {

        System.out.println(
                "\nDetected "
                        + matchedGroups.size()
                        + " matched groups:");

        matchedGroups.forEach(group -> {

            String nodeIds =
                    group.stream()
                            .map(v -> v.id().toString())
                            .sorted()
                            .collect(Collectors.joining(", "));
        });
    }


    // Helper method for threshold comparison
    private static boolean isClose(BigInteger a,
                                   BigInteger b,
                                   BigInteger threshold) {

        return a.subtract(b)
                .abs()
                .compareTo(threshold) <= 0;
    }
}
