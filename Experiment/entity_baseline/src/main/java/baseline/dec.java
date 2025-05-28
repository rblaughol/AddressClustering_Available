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

public class dec {

    private static List<Set<Vertex>> matchedGroups = new ArrayList<>();
    private static BigInteger dynamicThreshold = new BigInteger("10");

    public static void main(String[] args) {
        JanusGraph graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();
        SG1_dec_base sg1_processor = new SG1_dec_base();
        SG2_dec_base sg2_processor = new SG2_dec_base();
        List<String> addresses = readAddressesFromFile("Tokenadd.txt");
        String outputDir = "Tokenadd_proposed/";
        new File(outputDir).mkdirs();

        for (int i = 0; i < addresses.size(); i++) {
            String ClusterAdd = addresses.get(i);
            List<Set<Vertex>> allMatchedGroups = new ArrayList<>();
            boolean strict = true;

            // 处理初始地址
            matchedGroups.clear();
            List<Set<Vertex>> initGroups = sg1_processor.processInitAddress(ClusterAdd, g, "None", "None", strict);
            allMatchedGroups.addAll(initGroups);
            List<Set<Vertex>> midGroups = sg2_processor.processMidAddress(ClusterAdd, g, "None", "None", strict);
            allMatchedGroups.addAll(midGroups);

            // 处理DV地址
            List<Object> DVs = g.V().has("bulkLoader.vertex.id", ClusterAdd).bothE().values("source_address").toList();
            List<Object> uniqueDVs = DVs.stream().distinct().collect(Collectors.toList());
            for (Object dvObj : uniqueDVs) {
                String DV = dvObj.toString();
                matchedGroups.clear();
                List<Set<Vertex>> dvGroups = sg1_processor.processInitAddress(ClusterAdd, g, "TT", DV, strict);
                allMatchedGroups.addAll(dvGroups);
                List<Set<Vertex>> dvGroups_2 = sg2_processor.processMidAddress(ClusterAdd, g, "TT", DV, strict);
                allMatchedGroups.addAll(dvGroups_2);
            }

            // 写入结果文件
            writeGroupsToFile(allMatchedGroups, outputDir + ClusterAdd + ".out");
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
}