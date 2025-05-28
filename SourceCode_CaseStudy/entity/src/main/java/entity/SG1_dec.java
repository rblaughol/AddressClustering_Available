package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;
import java.math.BigInteger;
import java.util.*;
import java.util.stream.Collectors;

public class SG1_dec {
    // 用于存储所有匹配到的address
    private static List<Set<Vertex>> matchedGroups = new ArrayList<>();
    private static BigInteger dynamicThreshold = new BigInteger("10");

    public static List<Set<Vertex>> processInitAddress(String address, GraphTraversalSource g, String BH, String source_address, boolean strict) {
        try {
            // 找到给定的地址
            Vertex init_v = g.V().has("bulkLoader.vertex.id", address).next();
            // 根据给定地址查询出的交易和节点，根据出的节点查最终节点
            List<Vertex> deposits;
            if (source_address.equals("None")) {
                deposits = g.V(init_v).outE()  // 获取所有入边
                    .toList()  // 转为List<Edge>
                    .stream()
                    .filter(edge -> (!"TT".equals(edge.value("behaviour2")) && (!new BigInteger(edge.value("value").toString()).equals(BigInteger.ZERO))))  // 过滤边
                    .map(edge -> edge.inVertex())  
                    .distinct()  // 去重
                    .collect(Collectors.toList());
            } else {
                deposits = g.V(init_v).outE().has("behaviour2", BH).has("source_address", source_address).inV().dedup().toList();
            }
            for (Vertex deposit : deposits) {
                // 预构建区块号映射，对于一个存款地址，先记录入的所有交易
                TreeMap<BigInteger, List<Edge>> blockMap = new TreeMap<>();
                List<Edge> inEdges;
                if (source_address.equals("None")){
                    inEdges = g.V(deposit).inE().toList()
                    .stream()
                    .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                    .collect(Collectors.toList());
                } else {
                    inEdges = g.V(deposit).inE().has("behaviour2", BH).has("source_address", source_address).toList();
                }
                for (Edge inEdge : inEdges) {
                    if (!new BigInteger(inEdge.value("value").toString()).equals(BigInteger.ZERO)) {
                        BigInteger blockNum = new BigInteger(inEdge.value("block_number").toString());
                        blockMap.computeIfAbsent(blockNum, k -> new ArrayList<>()).add(inEdge);
                    }
                }
                
                BigInteger balance = BigInteger.ZERO;
                // 查询出的交易和地址，根据出帐的交易，分出子图
                List<Edge> sortedOutEdges;
                if (source_address.equals("None")){
                    sortedOutEdges = g.V(deposit).outE().toList()
                    .stream()
                    .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                    .collect(Collectors.toList());
                } else {
                    sortedOutEdges = g.V(deposit).outE().has("behaviour2", BH).has("source_address", source_address).toList();
                }
                // sortedOutEdges.sort(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())));
                sortedOutEdges = sortedOutEdges.stream()
                                    .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                                    .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                                    .collect(Collectors.toList());
                BigInteger lowerBound = BigInteger.ZERO;
                
                // 遍历交易分出的子图
                for (Edge outEdge : sortedOutEdges) {
                    final BigInteger currentUpper = new BigInteger(outEdge.value("block_number").toString());
                    // 高效范围查询，按范围查询入账边
                    Map<BigInteger, List<Edge>> subMap = blockMap.subMap(lowerBound, true, currentUpper, false);
                    lowerBound = currentUpper;
                    
                    // 入账边
                    List<Edge> relevantInEdges = subMap.values().stream()
                        .flatMap(List::stream)
                        .collect(Collectors.toList());
                    
                    // 计算入账金额
                    Set<Vertex> inNodes = new HashSet<>();
                    BigInteger sumIn = relevantInEdges.stream()
                        .map(e -> {
                            BigInteger val = new BigInteger(e.value("value").toString());
                            inNodes.add(e.outVertex());
                            return val;
                        })
                        .reduce(BigInteger.ZERO, BigInteger::add);

                    // 计算存款地址余额
                    BigInteger outValue = new BigInteger(outEdge.value("value").toString());
                    BigInteger balanceBefore = balance;
                    balance = balanceBefore.add(sumIn).subtract(outValue);

                    // 考虑0值情况（矿工）
                    if (balance.compareTo(BigInteger.ZERO) < 0) {
                        balance = BigInteger.ZERO;
                    }
                    
                    // 仅对initv做去匿名
                    boolean containsInitNode = inNodes.stream()
                        .anyMatch(v -> v.id().equals(init_v.id()));

                    if (containsInitNode) {
                    // if (containsInitNode && sumIn.compareTo(BigInteger.ZERO) > 0 && balanceBefore.compareTo(BigInteger.ZERO) > 0) {
                        if (strict) {
                             // 条件1：入账总额 ≈ 出账金额
                            if (isClose(relevantInEdges, sumIn, outValue, dynamicThreshold)) {
                                if (inNodes.size() >= 2) {
                                    addGroup(new HashSet<>(inNodes));  // 添加输入节点组
                                    // System.out.println("Found 1!");
                                    // System.out.println(inNodes);
                                    // System.out.println(deposit);
                                }
                            }

                            // 条件2：余额+入账 ≈ 出账
                            if (isClose(relevantInEdges, sumIn.add(balanceBefore), outValue, dynamicThreshold)) {
                                Set<Vertex> comboGroup = new HashSet<>(inNodes);
                                if (comboGroup.size() >= 2) {
                                    addGroup(comboGroup);
                                    // System.out.println(balanceBefore);
                                    // System.out.println("Found 2!");
                                }
                            }
                        } else {
                            if (isClose(relevantInEdges, sumIn, outValue, dynamicThreshold)) {
                                inNodes.add(deposit);
                                if (inNodes.size() >= 2) {
                                    addGroup(inNodes);  // 添加输入节点组
                                    // System.out.println("Found 1!");
                                    // System.out.println(inNodes);
                                    // System.out.println(deposit);
                                }
                            }

                            // 条件2：余额+入账 ≈ 出账
                            if (isClose(relevantInEdges, sumIn.add(balanceBefore), outValue, dynamicThreshold)) {
                                // Set<Vertex> comboGroup = new HashSet<>(inNodes);
                                inNodes.add(deposit);
                                if (inNodes.size() >= 2) {
                                    addGroup(inNodes);
                                    // System.out.println(inNodes);
                                    // System.out.println("Found 2!");
                                }
                            }
                        }
                    }
                }
            }
            
            System.out.println("Over Processing Init Address\n");
            // 输出所有匹配的组
            printAllGroups();
        } catch (Exception e) { 
            e.printStackTrace();
        }
        return matchedGroups;
    }


    public static List<Set<Vertex>> processDepositAddress(String address, GraphTraversalSource g, String BH, String source_address, boolean strict) {
        try {
            Vertex deposit = g.V().has("bulkLoader.vertex.id", address).next();
            // 预构建区块号映射，对于一个存款地址，先记录入的所有交易
            TreeMap<BigInteger, List<Edge>> blockMap = new TreeMap<>();
            List<Edge> inEdges;
            if (source_address.equals("None")){
                inEdges = g.V(deposit).inE().toList()
                .stream()
                .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                .collect(Collectors.toList());
            } else {
                inEdges = g.V(deposit).inE().has("behaviour2", BH).has("source_address", source_address).toList();
            }
            for (Edge inEdge : inEdges) {
                if (!new BigInteger(inEdge.value("value").toString()).equals(BigInteger.ZERO)) {
                    BigInteger blockNum = new BigInteger(inEdge.value("block_number").toString());
                    blockMap.computeIfAbsent(blockNum, k -> new ArrayList<>()).add(inEdge);
                }
            }

            BigInteger balance = BigInteger.ZERO;

            // 查询出的交易和地址，根据出帐的交易，分出子图
            List<Edge> sortedOutEdges;
            if (source_address.equals("None")) {
                sortedOutEdges = g.V(deposit).outE().toList()
                .stream()
                .filter(edge -> !"TT".equals(edge.value("behaviour2")))
                .collect(Collectors.toList());
            } else {
                sortedOutEdges = g.V(deposit).outE().has("behaviour2", BH).has("source_address", source_address).toList();
            }
            sortedOutEdges = sortedOutEdges.stream()
                                .filter(e -> !new BigInteger(e.value("value").toString()).equals(BigInteger.ZERO))
                                .sorted(Comparator.comparing(e -> new BigInteger(e.value("block_number").toString())))
                                .collect(Collectors.toList());
            BigInteger lowerBound = BigInteger.ZERO;
                

            for (Edge outEdge : sortedOutEdges) {
                final BigInteger currentUpper = new BigInteger(outEdge.value("block_number").toString());
                // 高效范围查询， 按范围查询入账边
                Map<BigInteger, List<Edge>> subMap = blockMap.subMap(lowerBound, true, currentUpper, false);
                lowerBound = currentUpper;
                // 入账边
                List<Edge> relevantInEdges = subMap.values().stream()
                    .flatMap(List::stream)
                    .collect(Collectors.toList());
                // 计算入账金额
                Set<Vertex> inNodes = new HashSet<>();
                BigInteger sumIn = relevantInEdges.stream()
                    .map(e -> {
                        BigInteger val = new BigInteger(e.value("value").toString());
                        inNodes.add(e.outVertex());
                        return val;
                    })
                    .reduce(BigInteger.ZERO, BigInteger::add);

                // 后续处理逻辑保持不变
                BigInteger outValue = new BigInteger(outEdge.value("value").toString());
                BigInteger balanceBefore = balance;
                balance = balanceBefore.add(sumIn).subtract(outValue);

                if (balance.compareTo(BigInteger.ZERO) < 0) {
                    balance = BigInteger.ZERO;
                }
                // if (sumIn.compareTo(BigInteger.ZERO) > 0 && balanceBefore.compareTo(BigInteger.ZERO) > 0) {
                // 无条件1. 条件2：余额+入账 ≈ 出账
                if (isClose(relevantInEdges, sumIn.add(balanceBefore), outValue, dynamicThreshold)) {
                    Set<Vertex> comboGroup = new HashSet<>(inNodes);
                    comboGroup.add(deposit);  // 包含当前deposit节点
                    if (comboGroup.size() >= 2){
                        addGroup(comboGroup);
                        // System.out.println(balanceBefore);
                        // System.out.println("Found 2!");
                    }
                }
                // }
            }
            // }
            
            System.out.println("Over Processing Init Address\n");
            // 输出所有匹配的组
            printAllGroups();
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

    private static boolean isClose(List<Edge> edges, BigInteger sumIn, BigInteger outValue, BigInteger threshold) {
        // 1. 计算边集合的非零最小值
        BigInteger minNonZeroValue = edges.stream()
            .map(e -> new BigInteger(e.value("value").toString()))
            .filter(v -> !v.equals(BigInteger.ZERO))
            .max(BigInteger::compareTo)
            .orElse(BigInteger.ZERO); // 如果全为零则返回0
        
        // 防御性检查：最小值必须为正数
        if (minNonZeroValue.compareTo(BigInteger.ZERO) <= 0) {
            return false;
        }
        
        // 2. 计算入账-出账的差值
        BigInteger difference = sumIn.subtract(outValue);
        
        // 3. 计算比值：(difference / minNonZeroValue) >= 10
        // 等价于 difference >= 10 * minNonZeroValue
        BigInteger mul_difference =  difference.multiply(threshold);

        return minNonZeroValue.compareTo(mul_difference) >= 0;
    }
}