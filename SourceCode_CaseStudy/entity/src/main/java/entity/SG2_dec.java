package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;
import java.math.BigInteger;
import java.util.*;
import java.util.stream.Collectors;
import static org.apache.tinkerpop.gremlin.process.traversal.Order.asc;
import static org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.__.__;

public class SG2_dec {
    // 用于存储所有匹配到的address
    private static List<Set<Vertex>> matchedGroups = new ArrayList<>();
    private static BigInteger dynamicThreshold = new BigInteger("10");

    public static List<Set<Vertex>> processMidAddress(String address, GraphTraversalSource g, String BH, String source_address, boolean strict) {
        try {
            // 查询给定地址
            Vertex MidAdd = g.V().has("bulkLoader.vertex.id", address).next();
            // step1. 根据给定的节点，查询time和value满足条件的入边和出边
            // 查询相关交易，并按区块号排序
            List<Edge> allEdges = new ArrayList<>();
            if (source_address.equals("None")) {
                // 使用流过滤 behaviour2 = BH 的边
                allEdges = g.V(MidAdd).bothE()
                    .toList()
                    .stream()
                    .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                    .collect(Collectors.toList());
            } else {
                g.V(MidAdd).bothE().has("behaviour2", BH).has("source_address", source_address).forEachRemaining(allEdges::add);
            }
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
                    BigInteger diff = inValue.subtract(outValue);
                    BigInteger minVal = inValue.min(outValue); // 取inValue和outValue的较小值
                    // System.out.println(diff);
                    // 差值比例计算
                    if (minVal.compareTo(diff.multiply(dynamicThreshold)) >= 0 && diff.compareTo(BigInteger.ZERO) >= 0) {
                        // 获取相关顶点
                        Vertex inSource = e1.outVertex();
                        Vertex outTarget = e2.inVertex();
                        // step 2. 根据入边和出边，查询交集节点。
                        // 获取inSource的所有出节点 和 outTarget的所有入节点的交集
                        List<Vertex> inSourceOuts;
                        List<Vertex> outTargetIns;
                        if (source_address.equals("None")) {
                            inSourceOuts = g.V(inSource).outE()  // 获取所有入边
                                .toList()  // 转为List<Edge>
                                .stream()
                                .filter(edge -> !"TT".equals(edge.value("behaviour2")))  // 过滤边
                                .map(edge -> edge.inVertex())  // 获取边的源顶点（根据边方向可能需要调整）
                                .distinct()  // 去重
                                .collect(Collectors.toList());
                                
                            outTargetIns = g.V(outTarget).inE()  // 获取所有入边
                                .toList()  // 转为List<Edge>
                                .stream()
                                .filter(edge -> !"TT".equals(edge.value("behaviour2")))  // 过滤边
                                .map(edge -> edge.outVertex())  // 获取边的源顶点（根据边方向可能需要调整）
                                .distinct()  // 去重
                                .collect(Collectors.toList());
                            
                        } else {
                            inSourceOuts = g.V(inSource).outE().has("behaviour2", BH).has("source_address", source_address).inV().dedup().toList();
                            outTargetIns = g.V(outTarget).inE().has("behaviour2", BH).has("source_address", source_address).outV().dedup().toList();
                        }
                        // List<Vertex> intersection = new ArrayList<>(inSourceOuts);
                        // intersection.retainAll(outTargetIns);
                        inSourceOuts.retainAll(outTargetIns);

                        // step 3. 对交集中的每个节点做value金额条件和time时间条件的判断
                        // 遍历交集节点进行深度验证
                        // System.out.println(inSourceOuts);
                        for (Vertex a : inSourceOuts) {
                            if (a != MidAdd){
                                // 处理相邻边对。
                                List<Edge> other_allEdges = new ArrayList<>();
                                if (source_address.equals("None")) {
                                    // 使用流过滤 behaviour2 = BH 的边
                                    other_allEdges = g.V(a).bothE()
                                        .toList()
                                        .stream()
                                        .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                                        .collect(Collectors.toList());
                                } else {
                                    g.V(a).bothE().has("behaviour2", BH).has("source_address", source_address).forEachRemaining(other_allEdges::add);
                                }
                                other_allEdges = other_allEdges.stream()
                                    .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                                    .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                                    .collect(Collectors.toList());
                                // other_allEdges.sort(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())));
                                // 检查相邻的入边和出边
                                for (int j = 0; j < other_allEdges.size() - 1; j++) {
                                    Edge other_e1 = other_allEdges.get(j);
                                    Edge other_e2 = other_allEdges.get(j + 1);
                                    boolean other_e1In = other_e1.inVertex().equals(a);
                                    boolean other_e2Out = other_e2.outVertex().equals(a);
                                    boolean other_e1Out = other_e1.outVertex().equals(inSource);
                                    boolean other_e2In = other_e2.inVertex().equals(outTarget);
                                    // boolean e1_zero = other_e1.value("value").equals(BigInteger.ZERO);
                                    // boolean e2_zero = other_e2.value("value").equals(BigInteger.ZERO);
                                    // 此节点满足和mid节点类似的图结构，且时间条件要满足
                                    if (other_e1In && other_e2Out && other_e1Out && other_e2In) {
                                        BigInteger other_invalue = new BigInteger(other_e1.value("value").toString());
                                        BigInteger other_outvalue = new BigInteger(other_e2.value("value").toString());
                                        // 金额计算
                                        BigInteger other_diff = other_invalue.subtract(other_outvalue);
                                        BigInteger other_minVal = other_invalue.min(other_outvalue);
                                        // 满足金额条件
                                        if (other_minVal.compareTo(other_diff.multiply(dynamicThreshold)) >= 0 && other_diff.compareTo(BigInteger.ZERO) >= 0) {
                                            // 创建新组并去重
                                            Set<Vertex> newGroup = new HashSet<>();
                                            if (strict) {
                                                newGroup.add(a);
                                                newGroup.add(MidAdd);
                                                addGroup(newGroup);
                                                // System.out.println(newGroup);
                                                // System.out.println("Find new complex clustering!!!");
                                                break;
                                            } else {
                                                newGroup.add(a);
                                                newGroup.add(MidAdd);
                                                newGroup.add(outTarget);
                                                addGroup(newGroup);
                                                // System.out.println(newGroup);
                                                // System.out.println("Find new complex clustering!!!");
                                                break;
                                            }
                                        }
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
                // List<Object> values = g.V(deposit).bothE().values("value").toList();
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
                            // System.out.println("Find complex vertices");
                            // System.out.println(group);
                        }
                    }
                }
            }
            // System.out.println("test!");
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
            
            // System.out.println("组节点: [" + nodeIds + "]");
        });
    }

    // 辅助方法保持代码整洁
    private static boolean isClose(BigInteger a, BigInteger b, BigInteger threshold) {
        return a.subtract(b).abs().compareTo(threshold) <= 0;
    }
}