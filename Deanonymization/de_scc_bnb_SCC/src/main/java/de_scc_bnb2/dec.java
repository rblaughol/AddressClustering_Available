package de_scc_bnb2;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;

import java.io.FileWriter;
import java.io.IOException;

public class dec {
    public static void main(String[] args) {
        String propertyFile = "/public/home/blockchain_2/slave2/deanonymization/de_scc_bnb2/janusgraph-hbase-solr-proposed.properties";
        JanusGraph graph = JanusGraphFactory.open(propertyFile);
        GraphTraversalSource g = graph.traversal();
        
        try (FileWriter writer = new FileWriter("/public/home/blockchain_2/slave2/deanonymization/de_scc_bnb2/edge.txt")) {
            // 遍历所有边，筛选属性behaviour1为"SCC"的边
            g.E().has("behaviour2", "SCC").forEachRemaining(edge -> {
                // 获取边的出节点和入节点
                Vertex outVertex = edge.outVertex();
                Vertex inVertex = edge.inVertex();
                
                // 获取节点的标识符（优先用node_id，否则用bulkLoader.vertex.id）
                String outId = getVertexIdentifier(outVertex);
                String inId = getVertexIdentifier(inVertex);
                
                try {
                    // 将两个节点的标识符写入文件，格式：outId,inId
                    writer.write(outId + "," + inId + "\n");
                } catch (IOException e) {
                    e.printStackTrace();
                }
            });
            System.out.println("处理完成！所有符合条件的边已写入文件。");
        } catch (IOException e) {
            e.printStackTrace();
        } finally {
            graph.close();
        }
    }
    
    // 辅助方法：获取顶点的标识符（优先node_id，其次bulkLoader.vertex.id）
    private static String getVertexIdentifier(Vertex vertex) {
        if (vertex.property("bulkLoader.vertex.id").isPresent()) {
            return vertex.value("bulkLoader.vertex.id").toString();
        } else {
            // 如果两个属性都不存在，抛出异常或返回顶点ID（根据需求调整）
            throw new RuntimeException("顶点缺少bulkLoader.vertex.id属性: " + vertex.id());
        }
    }
}