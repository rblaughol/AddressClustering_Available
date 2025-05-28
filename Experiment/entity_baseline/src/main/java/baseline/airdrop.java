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
        JanusGraph graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();
        
        List<String> addresses = readAddressesFromFile("Tokenadd.txt");
        String outputDir = "Tokenadd_airdrop/";
        new File(outputDir).mkdirs();

        for (int i = 0; i < addresses.size(); i++) {
            String ClusterAdd = addresses.get(i);
            List<Set<Vertex>> allMatchedGroups = new ArrayList<>();
            boolean strict = true;

            // 处理每个DV
            List<Object> DVs = g.V().has("bulkLoader.vertex.id", ClusterAdd)
                                .bothE().values("source_address").dedup().toList();
            for (Object dv : DVs) {
                String DV = dv.toString();
                matchedGroups.clear();
                
                // 处理中间地址
                List<Set<Vertex>> midTT = processMidAddress(ClusterAdd, g, "TT", DV, strict);
                // 处理接收地址
                List<Set<Vertex>> recTT = processRecAddress(ClusterAdd, g, "TT", DV, strict);
                
                allMatchedGroups.addAll(midTT);
                allMatchedGroups.addAll(recTT);
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
                if (!line.isEmpty()) addresses.add(line);
            }
        } catch (FileNotFoundException e) {
            e.printStackTrace();
        }
        return addresses;
    }

    private static void writeGroupsToFile(List<Set<Vertex>> groups, String filename) {
        try (PrintWriter writer = new PrintWriter(new FileWriter(filename))) {
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


    public static List<Set<Vertex>> processMidAddress(String address, GraphTraversalSource g, String BH, String source_address, boolean strict) {
        try {
            // 查询给定地址
            Vertex MidAdd = g.V().has("bulkLoader.vertex.id", address).next();
            // step1. 根据给定的节点，查询time和value满足条件的入边和出边
            // 查询相关交易，并按区块号排序
            List<Edge> allEdges = new ArrayList<>();
            g.V(MidAdd).bothE().has("behaviour2", BH).has("source_address", source_address).forEachRemaining(allEdges::add);
            // 将过滤后的边添加到最终的 allEdges 列表
            allEdges = allEdges.stream()
                .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                .collect(Collectors.toList());
            // 依此遍历排序的交易，找到相关的inall和outall的交易和地址
            for (int i = 0; i < allEdges.size() - 1; i++) {
                Edge e1 = allEdges.get(i);
                Edge e2 = allEdges.get(i + 1);
                boolean e1In = e1.inVertex().equals(MidAdd);
                boolean e2Out = e2.outVertex().equals(MidAdd);
                // 找到相邻边——时间条件
                if (e1In && e2Out) {
                    BigInteger inValue, outValue;
                    inValue = new BigInteger(e1.value("value").toString());
                    outValue = new BigInteger(e2.value("value").toString());
                    // 计算相邻边交易金额的差值——金额条件
                    // BigInteger diff = inValue.subtract(outValue);
                    // BigInteger minVal = inValue.min(outValue); // 取inValue和outValue的较小值
                    // System.out.println(diff);
                    // 差值比例计算
                    if (inValue.equals(outValue)) {
                        // 获取相关顶点
                        Vertex inSource = e1.outVertex();
                        Vertex outTarget = e2.inVertex();
                        // step 2. 根据入边和出边，查询交集节点。
                        // 获取inSource的所有出节点 和 outTarget的所有入节点的交集
                        // List<Vertex> inSourceOuts;
                        // List<Vertex> outTargetIns;
                        List<Vertex> inSourceOuts = g.V(inSource)
                            .outE()
                            .has("behaviour2", BH)
                            .has("source_address", source_address)
                            .toList()
                            .stream()
                            .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                            .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                            .map(Edge::inVertex)
                            .distinct()
                            .collect(Collectors.toList());
                        // 修改后的处理逻辑
                        for (int idx = 0; idx < inSourceOuts.size(); idx++) {
                            Vertex MidAdd2 = inSourceOuts.get(idx);
                            if (MidAdd2.equals(MidAdd)) continue; // 跳过自身

                            // 获取MidAdd2的所有相关边并按区块排序
                            List<Edge> midEdges = g.V(MidAdd2).bothE()
                                .has("behaviour2", BH)
                                .has("source_address", source_address)
                                .toList()
                                .stream()
                                .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                                .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                                .collect(Collectors.toList());

                            // 检查相邻边对是否符合结构
                            for (int j = 0; j < midEdges.size() - 1; j++) {
                                Edge prevEdge = midEdges.get(j);
                                Edge nextEdge = midEdges.get(j + 1);

                                // 验证边方向性
                                boolean isIncoming = prevEdge.inVertex().equals(MidAdd2) && 
                                                    prevEdge.outVertex().equals(inSource);
                                boolean isOutgoing = nextEdge.outVertex().equals(MidAdd2) && 
                                                    nextEdge.inVertex().equals(outTarget);

                                if (isIncoming && isOutgoing) {
                                    // 金额条件检查
                                    BigInteger inVal = new BigInteger(prevEdge.value("value").toString());
                                    BigInteger outVal = new BigInteger(nextEdge.value("value").toString());
                                    // BigInteger diff = inVal.subtract(outVal);
                                    
                                    if (inValue.equals(inVal) && inValue.equals(outVal)) {
                                        
                                        // 构建地址组
                                        Set<Vertex> cluster = new HashSet<>();
                                        cluster.add(MidAdd);
                                        cluster.add(MidAdd2);
                                        if (!strict) cluster.add(outTarget);
                                        
                                        addGroup(cluster);
                                        break; // 找到后跳出当前节点循环
                                    }
                                }
                            }
                        }
                    }
                }
            }
            System.out.println("Over Processing Mid Address\n");
            printAllGroups();
        } catch (Exception e) { 
            e.printStackTrace();
        }
        return matchedGroups;
    }



    public static List<Set<Vertex>> processRecAddress(String address, GraphTraversalSource g, String BH, String source_address, boolean strict) {
        try {
            Vertex RecAdd = g.V().has("bulkLoader.vertex.id", address).next();
            // 处理相邻边对, step1. 根据给定的节点，查询time和value满足条件的入边和出边。
            List<Vertex> MidV_list;
            if (source_address.equals("None")) {
                MidV_list = g.V(RecAdd).inE()  // 获取所有入边
                    .toList()  // 转为List<Edge>
                    .stream()
                    .filter(edge -> !"TT".equals(edge.value("behaviour2")))  // 过滤边
                    .map(edge -> edge.outVertex())  // 获取边的源顶点（根据边方向可能需要调整）
                    .distinct()  // 去重
                    .collect(Collectors.toList());
            } else {
                MidV_list = g.V(RecAdd).inE().has("behaviour2", BH).has("source_address", source_address).outV().dedup().toList();
            }
            for (int i = 0; i < MidV_list.size() - 1; i++) {
                // 处理相邻边对
                Vertex MidV = MidV_list.get(i);
                List<Edge> allEdges = new ArrayList<>();
                if (source_address.equals("None")) {
                    // 使用流过滤 behaviour2 = BH 的边
                    allEdges = g.V(MidV).bothE()
                        .toList()
                        .stream()
                        .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                        .collect(Collectors.toList());
                } else {
                    g.V(MidV).bothE().has("behaviour2", BH).has("source_address", source_address).forEachRemaining(allEdges::add);
                }
                // 将过滤后的边添加到最终的 allEdges 列表
                allEdges = allEdges.stream()
                    .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                    .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                    .collect(Collectors.toList());
                // 依此遍历排序的交易，找到相关的inall和outall的交易和地址
                for (int j = 0; j < allEdges.size() - 1; j++) {
                    Edge e1 = allEdges.get(j);
                    Edge e2 = allEdges.get(j + 1);

                    boolean e1In = e1.inVertex().equals(MidV);
                    boolean e2Out = e2.outVertex().equals(MidV);
                    boolean e2In = e2.inVertex().equals(RecAdd);
                    // 找到相邻边，time
                    if (e1In && e2Out && e2In) {
                        BigInteger inValue, outValue;
                        inValue = new BigInteger(e1.value("value").toString());
                        outValue = new BigInteger(e2.value("value").toString());

                        // 计算相邻边交易金额的差值，value
                        BigInteger diff = inValue.subtract(outValue);
                        BigInteger minVal = inValue.min(outValue); // 取inValue和outValue的较小值
                        // System.out.println(diff);
                        // 差值比例计算
                        if (minVal.compareTo(diff.multiply(dynamicThreshold)) >= 0 && diff.compareTo(BigInteger.ZERO) >= 0) {
                            // 获取相关顶点
                            Vertex inSource = e1.outVertex();
                            Vertex outTarget = e2.inVertex();
                            // 聚合Mid和outV
                            Set<Vertex> group = new HashSet<>();
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



    // 添加组并去重
    private static synchronized void addGroup(Set<Vertex> newGroup) {
        // 使用字符串ID进行重复判断
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


    // 格式化输出所有组
    private static void printAllGroups() {
        System.out.println("\n发现 " + matchedGroups.size() + " 个匹配组：");
        matchedGroups.forEach(group -> {
            String nodeIds = group.stream()
                .map(v -> v.id().toString())
                .sorted()
                .collect(Collectors.joining(", "));
        });
    }

    // 辅助方法保持代码整洁
    private static boolean isClose(BigInteger a, BigInteger b, BigInteger threshold) {
        return a.subtract(b).abs().compareTo(threshold) <= 0;
    }
}