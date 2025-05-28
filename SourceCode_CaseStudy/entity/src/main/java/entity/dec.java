package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.util.*;
import java.util.stream.Collectors;
import java.math.BigInteger;

public class dec {

    public static void main(String[] args) {
        JanusGraph graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/entity/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();
        String ClusterAdd = "6aacece3ed4d36995c209fa8e96fcf4300d192ba";
        SG1_dec sg1_processor = new SG1_dec();
        SG2_dec sg2_processor = new SG2_dec();
        boolean strict = true;

        // 存储所有匹配的组
        List<Set<Vertex>> allMatchedGroups = new ArrayList<>();

        // 处理初始子图
        List<Set<Vertex>> matchedGroups_Init = sg1_processor.processInitAddress(ClusterAdd, g, "None", "None", strict);
        allMatchedGroups.addAll(matchedGroups_Init);

        if (!strict) {
            List<Set<Vertex>> matchedGroups_Deposit = sg1_processor.processDepositAddress(ClusterAdd, g, "None", "None", strict);
            allMatchedGroups.addAll(matchedGroups_Deposit);
        }

        // 处理中间子图
        List<Set<Vertex>> matchedGroups_Mid = sg2_processor.processMidAddress(ClusterAdd, g, "None", "None", strict);
        allMatchedGroups.addAll(matchedGroups_Mid);

        if (!strict) {
            List<Set<Vertex>> matchedGroups_Rec = sg2_processor.processRecAddress(ClusterAdd, g, "None", "None", strict);
            allMatchedGroups.addAll(matchedGroups_Rec);
        }

        // 处理每个 DV 的情况
        List<Object> DVs = g.V().has("bulkLoader.vertex.id", ClusterAdd).bothE().values("source_address").toList();
        List<Object> uniqueDVs = DVs.stream().distinct().collect(Collectors.toList());
        for (int j = 0; j < uniqueDVs.size(); j++) {
            String DV = uniqueDVs.get(j).toString();

            List<Set<Vertex>> initTT = sg1_processor.processInitAddress(ClusterAdd, g, "TT", DV, strict);
            allMatchedGroups.addAll(initTT);

            if (!strict) {
                List<Set<Vertex>> depositTT = sg1_processor.processDepositAddress(ClusterAdd, g, "TT", DV, strict);
                allMatchedGroups.addAll(depositTT);
            }

            List<Set<Vertex>> midTT = sg2_processor.processMidAddress(ClusterAdd, g, "TT", DV, strict);
            allMatchedGroups.addAll(midTT);

            if (!strict) {
                List<Set<Vertex>> recTT = sg2_processor.processRecAddress(ClusterAdd, g, "TT", DV, strict);
                allMatchedGroups.addAll(recTT);
            }
        }

        // 写入文件
        try (BufferedWriter writer = new BufferedWriter(new FileWriter("case_Indiv6.txt"))) {
            for (Set<Vertex> group : allMatchedGroups) {
                List<String> addresses = new ArrayList<>();
                for (Vertex v : group) {
                    // 提取地址属性，假设属性名为 "address"
                    String address = v.value("bulkLoader.vertex.id");
                    addresses.add(address);
                }
                String line = String.join(",", addresses);
                writer.write(line);
                writer.newLine();
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        graph.close();
    }
}