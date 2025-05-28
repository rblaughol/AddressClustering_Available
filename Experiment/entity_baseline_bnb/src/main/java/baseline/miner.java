package entity;

import org.apache.tinkerpop.gremlin.structure.Edge;
import org.apache.tinkerpop.gremlin.structure.Graph;
import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.janusgraph.core.JanusGraphFactory;
import org.janusgraph.core.JanusGraph;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.hbase.HBaseConfiguration;
import java.util.List;
import java.util.*;
import java.io.File;

public class miner {
    public static void main(String[] args) {
        // 存储所有子进程
        List<Process> processes = new ArrayList<>();

        String classpath = "miner_son.jar";
        String className = "degreeCalc.degreeCalc";
        
        for (int i = 0; i < 10; i++) {
            try {
                // 创建ProcessBuilder实例
                ProcessBuilder pb = new ProcessBuilder("java", "-cp", classpath, className, (i * 200000) + "", ((i+1) * 200000) + "");

                // 设置输出重定向
                pb.redirectOutput(new File("./multiProcessLogs/" + i + ".out"));

                // 启动进程
                Process process = pb.start();
                
                // 将进程添加到列表中，以便后续管理（如等待它们完成）
                processes.add(process);
                
            } catch (IOException e) {
                e.printStackTrace();
            }
        }

        // 可选：等待所有子进程完成
        for (Process p : processes) {
            try {
                p.waitFor();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }

}