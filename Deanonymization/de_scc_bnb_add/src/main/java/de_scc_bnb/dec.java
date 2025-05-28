package de_scc_bnb;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Graph;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;

import java.io.FileWriter;
import java.io.IOException;
import java.util.List;

public class dec {
    public static void main(String[] args) {
        String propertyFile = "/public/home/blockchain_2/slave2/deanonymization/de_scc_bnb/janusgraph-hbase-solr-proposed.properties";
        JanusGraph graph = JanusGraphFactory.open(propertyFile);
        GraphTraversalSource g = graph.traversal();
        
        try (FileWriter writer = new FileWriter("/public/home/blockchain_2/slave2/deanonymization/de_scc_bnb/add.txt")) {
            g.V().forEachRemaining(node -> {
                // Check if the node has the "node_id" property
                if (!node.properties("node_id").hasNext()) {
                    System.out.println(node.id());
                    // Check if the node has the "bulkLoader.vertex.id" property
                    if (node.properties("bulkLoader.vertex.id").hasNext()) {
                        Object bulkLoaderId = node.value("bulkLoader.vertex.id");
                        try {
                            // Write the node ID
                            writer.write(bulkLoaderId.toString());
                            System.out.println(bulkLoaderId.toString());
                            // Write a new line
                            writer.write("\n");
                            System.out.println("over!!");
                        } catch (IOException e) {
                            e.printStackTrace();
                        }
                    }
                }
            });
            System.out.println("over!!!");
        } catch (IOException e) {
            e.printStackTrace();
        } finally {
            graph.close();
        }
    }
}
