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
        // 1. 打开图数据库连接
        JanusGraph graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();
        List<Object> addresses = new ArrayList<>();
        

        // List<Object> init_addresses = new ArrayList<>();
        // Set<Object> addresses = new HashSet<>();
        // Set<String> exchangeAddrs = new HashSet<>();
        // String filePath = "exchanges.csv";
        // try (BufferedReader br = new BufferedReader(new FileReader(filePath))) {
        //     br.readLine(); // 跳过标题
        //     String line;
        //     while ((line = br.readLine()) != null) {
        //         String[] parts = line.split(",", 2);
        //         if (parts.length > 0) {
        //             exchangeAddrs.add(parts[0].trim());
        //         }
        //     }
        // } catch (IOException e) {
        //     System.err.println("读取CSV失败: " + e.getMessage());
        // }
        // for (String exchangeAddr : exchangeAddrs) {
        //     // System.out.println(exchangeAddr);
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

        System.out.println("共发现 " + addresses.size() + " 个有效节点");

        // 3. 随机抽样（处理节点不足的情况）
        int sampleSize = Math.min(100, addresses.size());
        if (sampleSize == 0) {
            System.out.println("警告：未找到任何有效节点");
            graph.close();
            return;
        }

        List<Object> randomSample = new ArrayList<>(addresses);
        Collections.shuffle(randomSample);
        randomSample = randomSample.subList(0, sampleSize);

        // 4. 写入文件（带异常处理）
        try (BufferedWriter writer = new BufferedWriter(new FileWriter("Tokenadd.txt"))) {
            for (Object address : randomSample) {
                writer.write(address.toString());
                writer.newLine();
            }
            System.out.println("成功写入 " + sampleSize + " 个随机地址到 Randomadd.txt");
        } catch (Exception e) {
            System.err.println("文件写入失败: " + e.getMessage());
            e.printStackTrace();
        }

        // 5. 关闭图连接
        graph.close();
    }
}