package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.util.*;
import java.util.stream.Collectors;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;

public class RandomAdd {

    public static void main(String[] args) {
        // 1. Open graph database connection
        JanusGraph graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();
        List<Object> addresses = new ArrayList<>();
        

        // List<Object> init_addresses = new ArrayList<>();
        // Set<Object> addresses = new HashSet<>();
        // Set<String> exchangeAddrs = new HashSet<>();
        // String filePath = "exchanges.csv";
        // try (BufferedReader br = new BufferedReader(new FileReader(filePath))) {
        //     br.readLine(); // Skip header
        //     String line;
        //     while ((line = br.readLine()) != null) {
        //         String[] parts = line.split(",", 2);
        //         if (parts.length > 0) {
        //             exchangeAddrs.add(parts[0].trim());
        //         }
        //     }
        // } catch (IOException e) {
        //     System.err.println("Failed to read CSV: " + e.getMessage());
        // }
        // for (String exchangeAddr : exchangeAddrs) {
        //     init_addresses = g.V()
        //         .has("bulkLoader.vertex.id", exchangeAddr)
        //         .in()
        //         .in()
        //         .dedup()
        //         .values("bulkLoader.vertex.id")
        //         .toList();

        //     addresses.addAll(init_addresses);
        // }

        // 
        // addresses = g.V().has("bulkLoader.vertex.id").dedup().limit(10000).values("bulkLoader.vertex.id").toList();
        // addresses = g.E().has("behaviour2","TT").bothV().dedup().limit(10000).values("bulkLoader.vertex.id").toList();
        addresses = g.E().has("behaviour2","TT").bothV().dedup().limit(100000).values("bulkLoader.vertex.id").toList();

        System.out.println("Found " + addresses.size() + " valid vertices");

        // 3. Random sampling (handle case where total nodes are fewer than sample size)
        int sampleSize = Math.min(100, addresses.size());
        if (sampleSize == 0) {
            System.out.println("Warning: No valid vertices found");
            graph.close();
            return;
        }

        List<Object> randomSample = new ArrayList<>(addresses);
        Collections.shuffle(randomSample);
        randomSample = randomSample.subList(0, sampleSize);

        // 4. Write to file (with exception handling)
        try (BufferedWriter writer = new BufferedWriter(new FileWriter("Tokenadd.txt"))) {
            for (Object address : randomSample) {
                writer.write(address.toString());
                writer.newLine();
            }
            System.out.println("Successfully wrote " + sampleSize + " random addresses to Randomadd.txt");
        } catch (Exception e) {
            System.err.println("File write failed: " + e.getMessage());
            e.printStackTrace();
        }

        // 5. Close graph connection
        graph.close();
    }
}
