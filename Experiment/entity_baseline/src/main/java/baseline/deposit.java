package entity;

import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Vertex;
import org.janusgraph.core.JanusGraph;
import org.janusgraph.core.JanusGraphFactory;
import java.math.BigInteger;
import java.util.*;
import java.util.stream.Collectors;
import java.io.*;

public class deposit {
    private static BigInteger dynamicThreshold = new BigInteger("10");
    private static Set<String> exchangeAddresses = new HashSet<>();
    private static Set<String> minerAddresses = new HashSet<>();
    private static Set<Set<Vertex>> matchedGroups = new HashSet<>();

    static {
        loadAddressData("exchanges.csv", exchangeAddresses, true);
        loadAddressData("miners_eth.txt", minerAddresses, false);
    }

    public static void main(String[] args) {
        JanusGraph graph = JanusGraphFactory.open("/public/home/blockchain_2/slave2/deanonymization/entity_baseline/janusgraph-hbase-solr-proposed.properties");
        GraphTraversalSource g = graph.traversal();

        // 从文件读取地址列表
        List<String> addresses = readAddressesFromFile("Tokenadd.txt");
        String outputDir = "Tokenadd_deposit/";
        new File(outputDir).mkdirs();

        for (int i = 0; i < addresses.size(); i++) {
            String clusterAdd = addresses.get(i);
            matchedGroups.clear(); // 清空之前的匹配结果

            System.out.println("Processing address: " + clusterAdd);
            processAddress(clusterAdd, g, outputDir + clusterAdd + ".out");
        }

        graph.close();
    }

    private static void processAddress(String address, GraphTraversalSource g, String outputFile) {
        try {
            // 处理初始地址
            processInitAddress(address, g, "None", "None", true);
            
            // 获取并写入弱连通分量
            Vertex initVertex = g.V().has("bulkLoader.vertex.id", address).next();
            Set<Vertex> wcc = findWeaklyConnectedComponent(initVertex, matchedGroups);
            writeWCCToFile(wcc, outputFile);
        } catch (Exception e) {
            System.err.println("Error processing address: " + address);
            e.printStackTrace();
        }
    }

    // 新增方法：批量读取地址文件
    private static List<String> readAddressesFromFile(String filename) {
        List<String> addresses = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(filename))) {
            String line;
            while ((line = br.readLine()) != null) {
                addresses.add(line.trim());
            }
            System.out.println("Loaded " + addresses.size() + " addresses from file");
        } catch (IOException e) {
            System.err.println("Error reading address file:");
            e.printStackTrace();
        }
        return addresses;
    }

    // 优化后的地址加载方法
    private static void loadAddressData(String filename, Set<String> targetSet, boolean isCSV) {
        try (BufferedReader br = new BufferedReader(new FileReader(filename))) {
            if (isCSV) br.readLine(); // 跳过CSV标题行
            String line;
            while ((line = br.readLine()) != null) {
                String address = isCSV ? line.split(",")[0].trim() : line.trim();
                targetSet.add(address.toLowerCase());
            }
            System.out.println("Loaded " + targetSet.size() + " addresses from " + filename);
        } catch (IOException e) {
            System.err.println("Error loading address data:");
            e.printStackTrace();
        }
    }

    public static Set<Set<Vertex>> processInitAddress(String address, GraphTraversalSource g, String BH, String sourceAddress, boolean strict) {
        // List<Set<Vertex>> matchedGroups = new ArrayList<>();
        try {
            Vertex initVertex = g.V().has("bulkLoader.vertex.id", address).next();
            List<Edge> initOutEdges;

            if (sourceAddress.equals("None")) {
                initOutEdges = g.V(initVertex).outE().toList().stream()
                    .filter(edge -> !"TT".equals(edge.value("behaviour2")) && 
                           !new BigInteger(edge.value("value").toString()).equals(BigInteger.ZERO))
                    .collect(Collectors.toList());
            } else {
                initOutEdges = g.V(initVertex).outE()
                    .has("behaviour2", BH)
                    .has("source_address", sourceAddress)
                    .toList();
            }

            List<Vertex> deposits = initOutEdges.stream()
                .map(edge -> edge.inVertex())
                .distinct()
                .collect(Collectors.toList());

            for (Vertex deposit : deposits) {
                // 检查deposit是否属于交易所
                String depositAddr = (String) deposit.value("bulkLoader.vertex.id");
                if (depositAddr == null || exchangeAddresses.contains(depositAddr.toLowerCase())) {
                    continue;
                }

                List<Edge> inEdges;
                if (sourceAddress.equals("None")) {
                    inEdges = g.V(deposit).inE().toList().stream()
                        .filter(edge -> !"TT".equals(edge.value("behaviour2")) && 
                               !new BigInteger(edge.value("value").toString()).equals(BigInteger.ZERO))
                        .collect(Collectors.toList());
                } else {
                    inEdges = g.V(deposit).inE()
                        .has("behaviour2", BH)
                        .has("source_address", sourceAddress)
                        .toList();
                }

                List<Edge> outEdges;
                if (sourceAddress.equals("None")) {
                    outEdges = g.V(deposit).outE().toList().stream()
                        .filter(edge -> !"TT".equals(edge.value("behaviour2")) && 
                               !new BigInteger(edge.value("value").toString()).equals(BigInteger.ZERO))
                        .collect(Collectors.toList());
                } else {
                    outEdges = g.V(deposit).outE()
                        .has("behaviour2", BH)
                        .has("source_address", sourceAddress)
                        .toList();
                }

                for (Edge inEdge : inEdges) {
                    for (Edge outEdge : outEdges) {
                        int blockIn = Integer.parseInt(inEdge.value("block_number").toString());
                        int blockOut = Integer.parseInt(outEdge.value("block_number").toString());
                        BigInteger valueIn = new BigInteger(inEdge.value("value").toString());
                        BigInteger valueOut = new BigInteger(outEdge.value("value").toString());
                        BigInteger valueDiff = valueIn.subtract(valueOut);
                        // System.out.println(valueDiff);
                        final BigInteger ETH_THRESHOLD = new BigInteger("10000000000000000");
                        // System.out.println(blockIn);

                        if ((blockIn - blockOut) < 3200 && valueDiff.compareTo(ETH_THRESHOLD) <= 0) {
                            // System.out.println("satisfied!");
                            Vertex inNode = inEdge.outVertex();
                            Vertex outNode = outEdge.inVertex();

                            // 检查inNode是否属于交易所或矿工
                            String inNodeAddr = (String) inNode.value("bulkLoader.vertex.id");
                            if (inNodeAddr == null || 
                                exchangeAddresses.contains(inNodeAddr.toLowerCase()) ||
                                minerAddresses.contains(inNodeAddr.toLowerCase())) {
                                // exchangeAddresses.contains(inNodeAddr.toLowerCase())) {
                                continue;
                            }

                            // 检查outNode是否属于交易所
                            String outNodeAddr = (String) outNode.value("bulkLoader.vertex.id");
                            if (outNodeAddr == null || !exchangeAddresses.contains(outNodeAddr.toLowerCase())) {
                                continue;     
                            }

                            Set<Vertex> group = new LinkedHashSet<>();
                            group.add(inNode);
                            group.add(deposit);
                            matchedGroups.add(group);
                            // System.out.println(matchedGroups.size());
                        }
                    }
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return matchedGroups;
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
    // 基于 matchedGroups 中的组结构查找弱连通分量
    private static Set<Vertex> findWeaklyConnectedComponent(Vertex initVertex, Set<Set<Vertex>> matchedGroups) {
        Map<Vertex, Set<Vertex>> adjacencyList = new HashMap<>();
        Set<Vertex> allNodes = new HashSet<>();

        // 构建邻接表
        for (Set<Vertex> group : matchedGroups) {
            List<Vertex> nodes = new ArrayList<>(group);
            allNodes.addAll(nodes);
            // 组内节点两两相连
            for (int i = 0; i < nodes.size(); i++) {
                Vertex node1 = nodes.get(i);
                for (int j = i + 1; j < nodes.size(); j++) {
                    Vertex node2 = nodes.get(j);
                    adjacencyList.computeIfAbsent(node1, k -> new HashSet<>()).add(node2);
                    adjacencyList.computeIfAbsent(node2, k -> new HashSet<>()).add(node1);
                }
            }
        }

        // 如果 initVertex 不在节点集合中，返回空集
        if (!allNodes.contains(initVertex)) {
            return Collections.emptySet();
        }

        // BFS遍历
        Set<Vertex> visited = new HashSet<>();
        Queue<Vertex> queue = new LinkedList<>();
        queue.add(initVertex);
        visited.add(initVertex);

        while (!queue.isEmpty()) {
            Vertex current = queue.poll();
            for (Vertex neighbor : adjacencyList.getOrDefault(current, Collections.emptySet())) {
                if (!visited.contains(neighbor)) {
                    visited.add(neighbor);
                    queue.add(neighbor);
                }
            }
        }

        return visited;
    }

    // 写入文件
    private static void writeWCCToFile(Set<Vertex> wcc, String filename) {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(filename))) {
            for (Vertex v : wcc) {
                String address = (String) v.value("bulkLoader.vertex.id");
                writer.write(address + "\n");
            }
            System.out.println("弱连通分量已写入文件: " + filename);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}