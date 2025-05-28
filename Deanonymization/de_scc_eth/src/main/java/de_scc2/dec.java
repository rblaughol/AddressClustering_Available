package de_scc2;

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
        String propertyFile = "/public/home/blockchain_2/slave2/deanonymization/de_scc2/janusgraph-hbase-solr-proposed.properties";
        JanusGraph graph = JanusGraphFactory.open(propertyFile);
        JanusGraph graph2 = JanusGraphFactory.open(propertyFile);
        GraphTraversalSource g = graph.traversal();
        
        try (FileWriter writer = new FileWriter("/public/home/blockchain_2/slave2/deanonymization/de_scc2/add.txt")) {
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
                            // Check adjacent edges
                            GraphTraversalSource g2 = graph2.traversal();
                            List<Vertex> adjacentNodes = g2.V().has("bulkLoader.vertex.id",bulkLoaderId.toString()).outE().has("behaviour2", "SCC").inV().toList();
                            System.out.println(adjacentNodes);
                            // Use a standard for-each loop to iterate over adjacent nodes
                            for (Vertex adjacentNode : adjacentNodes) {
                                // Check if the adjacent node has the "bulkLoader.vertex.id" property
                                if (adjacentNode.properties("bulkLoader.vertex.id").hasNext()) {
                                    Object adjacentBulkLoaderId = adjacentNode.value("bulkLoader.vertex.id");
                                    try {
                                        writer.write("," + adjacentBulkLoaderId.toString());
                                    } catch (IOException e) {
                                        e.printStackTrace();
                                    }
                                }
                            }
                            g2.tx().commit();
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
