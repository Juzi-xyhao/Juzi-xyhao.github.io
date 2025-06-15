---
title: SkyWalking链路追踪原理概述
categories: [分布式,链路追踪]
author:  xyhao
keywords: 主要对其插桩及链路追踪原理的概述
description: 主要对其插桩及链路追踪原理的概述
comments: true
date: 2024-12-20 11:00:00
abbrlink: '0'
copyright_author: 
copyright_url: 
top_img: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/articleCover/SkyWalking.png
cover: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/articleCover/SkyWalking.png
tags:
- RPC
- 链路追踪
---


> 之前博客里发过字节跳动技术团队的一篇文章：  
> [如何优雅地重试](https://juziblog.space/2024/10/18/2024-10-18-%E5%A6%82%E4%BD%95%E4%BC%98%E9%9B%85%E5%9C%B0%E9%87%8D%E8%AF%95/)  
> 看完后把他们对超时和重试场景下的优化写进了简历里  
> 但准备话术时发现了一个问题：  
> 结合全链路超时控制无效重试  
> 链路从哪来？  
> 网上很多的RPC框架都只是单对单的发RPC，虽然逻辑上存在链路但是这些框架并没有搭建出来  
> 于是我找来了链路追踪组件SkyWalking的[源码](https://github.com/apache/skywalking-java)  
> 通过看源码的方式终于知道了链路搭建的原理
> 


<h3 id="HLqgt">skywalking里的插件有什么用？</h3>
对某服务的插桩。插桩之后才能实现链路追踪。

插桩就是字节码增强，一个意思。

<h4 id="K1i9R">如何自定义插件？</h4>
见官方文档  
[插件开发指南](https://skywalking.apache.org/docs/skywalking-java/next/en/setup/service-agent/java-agent/java-plugin-development-guide/)

### 自定义类加载器
如果看过skywalking的源码就会发现，里面很多类都是通过自定义类加载器加载的。
为什么要自定义类加载器呢？  

**为了隔离资源，避免依赖冲突。**   

每个类加载器都有自己的加载路径。不同路径下的资源不能互相加载。这也是双亲委派机制的由来。  
对于同一份字节码，由不同的类加载器加载，加载出的两个实例不相同。如果一个项目里引入了不同的组件，比如每个组件都有log4j的库，但是版本不同。使用不同的类加载器就能避免因为类的全限定路径相同而导致不同的组件使用相同的log4j，也就避免了依赖冲突。

一个自定义类加载器的demo如下：

```java
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

public class MyClassLoader extends ClassLoader {

    private String classDir;

    public MyClassLoader(String classDir) {
        this.classDir = classDir;
    }

    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        byte[] classData = loadClassData(name);
        if (classData == null) {
            throw new ClassNotFoundException();
        } else {
            return defineClass(name, classData, 0, classData.length);
        }
    }

    private byte[] loadClassData(String className) {
        String fileName = classDir + File.separatorChar
                + className.replace('.', File.separatorChar) + ".class";
        try (FileInputStream fis = new FileInputStream(fileName);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            int b;
            while ((b = fis.read()) != -1) {
                baos.write(b);
            }
            return baos.toByteArray();
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    public static void main(String[] args) {
        try {
            // 实例化自定义类加载器并指定要加载类的根目录
            MyClassLoader classLoader = new MyClassLoader("/path/to/classes/");

            /*
             * 使用自定义类加载器加载该类，将该类的信息加载进JVM的方法区里。
             * 也就是俗称的三步走：加载、链接（验证、准备、解析）、初始化
             */
            Class<?> helloWorldClass = classLoader.loadClass("HelloWorld");
            
            // 创建实例并调用方法
            Object instance = helloWorldClass.getDeclaredConstructor().newInstance();
            helloWorldClass.getMethod("sayHello").invoke(instance);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

<h3 id="k3u2d">插桩，如何实现？</h3>
这是SkyWalking实现插桩的核心类：



```java
/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

package org.apache.skywalking.apm.agent.core.plugin;

import net.bytebuddy.description.type.TypeDescription;
import net.bytebuddy.dynamic.DynamicType;
import org.apache.skywalking.apm.agent.core.logging.api.ILog;
import org.apache.skywalking.apm.agent.core.logging.api.LogManager;
import org.apache.skywalking.apm.agent.core.plugin.interceptor.ConstructorInterceptPoint;
import org.apache.skywalking.apm.agent.core.plugin.interceptor.InstanceMethodsInterceptPoint;
import org.apache.skywalking.apm.agent.core.plugin.interceptor.StaticMethodsInterceptPoint;
import org.apache.skywalking.apm.agent.core.plugin.interceptor.enhance.ClassEnhancePluginDefine;
import org.apache.skywalking.apm.agent.core.plugin.interceptor.v2.InstanceMethodsInterceptV2Point;
import org.apache.skywalking.apm.agent.core.plugin.interceptor.v2.StaticMethodsInterceptV2Point;
import org.apache.skywalking.apm.agent.core.plugin.match.ClassMatch;
import org.apache.skywalking.apm.agent.core.util.CollectionUtil;
import org.apache.skywalking.apm.util.StringUtil;

import java.util.List;

/**
 * Basic abstract class of all sky-walking auto-instrumentation plugins.
 * <p>
 * It provides the outline of enhancing the target class. If you want to know more about enhancing, you should go to see
 * {@link ClassEnhancePluginDefine}
 */
public abstract class AbstractClassEnhancePluginDefine {
    private static final ILog LOGGER = LogManager.getLogger(AbstractClassEnhancePluginDefine.class);

    /**
     * plugin name defined in skywalking-plugin.def
     */
    private String pluginName;
    /**
     * New field name.
     */
    public static final String CONTEXT_ATTR_NAME = "_$EnhancedClassField_ws";

    /**
     * Main entrance of enhancing the class.
     *
     * @param typeDescription target class description.
     * @param builder         byte-buddy's builder to manipulate target class's bytecode.
     * @param classLoader     load the given transformClass
     * @return the new builder, or <code>null</code> if not be enhanced.
     * @throws PluginException when set builder failure.
     */
    public DynamicType.Builder<?> define(TypeDescription typeDescription, DynamicType.Builder<?> builder,
        ClassLoader classLoader, EnhanceContext context) throws PluginException {
        String interceptorDefineClassName = this.getClass().getName();
        String transformClassName = typeDescription.getTypeName();
        if (StringUtil.isEmpty(transformClassName)) {
            LOGGER.warn("classname of being intercepted is not defined by {}.", interceptorDefineClassName);
            return null;
        }

        LOGGER.debug("prepare to enhance class {} by {}.", transformClassName, interceptorDefineClassName);
        WitnessFinder finder = WitnessFinder.INSTANCE;
        /**
         * find witness classes for enhance class
         */
        String[] witnessClasses = witnessClasses();
        if (witnessClasses != null) {
            for (String witnessClass : witnessClasses) {
                if (!finder.exist(witnessClass, classLoader)) {
                    LOGGER.warn("enhance class {} by plugin {} is not activated. Witness class {} does not exist.", transformClassName, interceptorDefineClassName, witnessClass);
                    return null;
                }
            }
        }
        List<WitnessMethod> witnessMethods = witnessMethods();
        if (!CollectionUtil.isEmpty(witnessMethods)) {
            for (WitnessMethod witnessMethod : witnessMethods) {
                if (!finder.exist(witnessMethod, classLoader)) {
                    LOGGER.warn("enhance class {} by plugin {} is not activated. Witness method {} does not exist.", transformClassName, interceptorDefineClassName, witnessMethod);
                    return null;
                }
            }
        }

        /**
         * find origin class source code for interceptor
         */
        DynamicType.Builder<?> newClassBuilder = this.enhance(typeDescription, builder, classLoader, context);

        context.initializationStageCompleted();
        LOGGER.debug("enhance class {} by {} completely.", transformClassName, interceptorDefineClassName);

        return newClassBuilder;
    }

    /**
     * Begin to define how to enhance class. After invoke this method, only means definition is finished.
     *
     * @param typeDescription target class description
     * @param newClassBuilder byte-buddy's builder to manipulate class bytecode.
     * @return new byte-buddy's builder for further manipulation.
     */
    protected DynamicType.Builder<?> enhance(TypeDescription typeDescription, DynamicType.Builder<?> newClassBuilder,
                                             ClassLoader classLoader, EnhanceContext context) throws PluginException {
        newClassBuilder = this.enhanceClass(typeDescription, newClassBuilder, classLoader);

        newClassBuilder = this.enhanceInstance(typeDescription, newClassBuilder, classLoader, context);

        return newClassBuilder;
    }

    /**
     * Enhance a class to intercept constructors and class instance methods.
     *
     * @param typeDescription target class description
     * @param newClassBuilder byte-buddy's builder to manipulate class bytecode.
     * @return new byte-buddy's builder for further manipulation.
     */
    protected abstract DynamicType.Builder<?> enhanceInstance(TypeDescription typeDescription,
                                                     DynamicType.Builder<?> newClassBuilder, ClassLoader classLoader,
                                                     EnhanceContext context) throws PluginException;

    /**
     * Enhance a class to intercept class static methods.
     *
     * @param typeDescription target class description
     * @param newClassBuilder byte-buddy's builder to manipulate class bytecode.
     * @return new byte-buddy's builder for further manipulation.
     */
    protected abstract DynamicType.Builder<?> enhanceClass(TypeDescription typeDescription, DynamicType.Builder<?> newClassBuilder,
                                                  ClassLoader classLoader) throws PluginException;

    /**
     * Define the {@link ClassMatch} for filtering class.
     *
     * @return {@link ClassMatch}
     */
    protected abstract ClassMatch enhanceClass();

    /**
     * Witness classname list. Why need witness classname? Let's see like this: A library existed two released versions
     * (like 1.0, 2.0), which include the same target classes, but because of version iterator, they may have the same
     * name, but different methods, or different method arguments list. So, if I want to target the particular version
     * (let's say 1.0 for example), version number is obvious not an option, this is the moment you need "Witness
     * classes". You can add any classes only in this particular release version ( something like class
     * com.company.1.x.A, only in 1.0 ), and you can achieve the goal.
     */
    protected String[] witnessClasses() {
        return new String[] {};
    }

    protected List<WitnessMethod> witnessMethods() {
        return null;
    }

    public boolean isBootstrapInstrumentation() {
        return false;
    }

    /**
     * Constructor methods intercept point. See {@link ConstructorInterceptPoint}
     *
     * @return collections of {@link ConstructorInterceptPoint}
     */
    public abstract ConstructorInterceptPoint[] getConstructorsInterceptPoints();

    /**
     * Instance methods intercept point. See {@link InstanceMethodsInterceptPoint}
     *
     * @return collections of {@link InstanceMethodsInterceptPoint}
     */
    public abstract InstanceMethodsInterceptPoint[] getInstanceMethodsInterceptPoints();

    /**
     * Instance methods intercept v2 point. See {@link InstanceMethodsInterceptV2Point}
     *
     * @return collections of {@link InstanceMethodsInterceptV2Point}
     */
    public abstract InstanceMethodsInterceptV2Point[] getInstanceMethodsInterceptV2Points();

    /**
     * Static methods intercept point. See {@link StaticMethodsInterceptPoint}
     *
     * @return collections of {@link StaticMethodsInterceptPoint}
     */
    public abstract StaticMethodsInterceptPoint[] getStaticMethodsInterceptPoints();

    /**
     * Instance methods intercept v2 point. See {@link InstanceMethodsInterceptV2Point}
     *
     * @return collections of {@link InstanceMethodsInterceptV2Point}
     */
    public abstract StaticMethodsInterceptV2Point[] getStaticMethodsInterceptV2Points();

    /**
     * plugin name should be set after create PluginDefine instance
     *
     * @param pluginName key defined in skywalking-plugin.def
     */
    protected void setPluginName(final String pluginName) {
        this.pluginName = pluginName;
    }

    public String getPluginName() {
        return pluginName;
    }
}

```



类里那些方法都是从64行的define方法开始的。而define方法在`org.apache.skywalking.apm.agent.SkyWalkingAgent#premain`方法中被间接调用。

premain，顾名思义，在main方法执行前执行，这印证了SkyWalking是静态启动，而不是像arthas那样动态附加。

完整的调用链如下：

->`premain()`

->`installClassTransformer()`,此方法中,内部类`Transformer`被注入`agentBuilder`

->`Transformer.tranform()`

->`define()`

> `AgentBuilder` 是 `ByteBuddy` 提供的用于构建字节码转换操作的核心类之一，它会在后续按照设定的规则和配置来执行字节码增强的流程，而 `transform` 方法的作用就是指定具体由谁（ `Transformer` 实例）来对匹配到的目标类进行字节码的转换操作
>

define方法开始的调用链的具体流程如下：

1. 准备工作。验证各个参数合法性
2. 见证类验证。确定中间件的版本。因为没有任何方法可以百分百获取系统中某个中间件的版本号。但是每个版本都会有一些独特的类。通过排列组合可以间接确定版本号。
3. 增强静态和实例方法。在enhance方法中调了两个抽象方法。一个负责增强目标类的静态方法，另一个负责实例方法。具体的增强逻辑由子类使用`DynamicType.Builder<?>`（`Byte Buddy` 提供的用于构建和修改字节码的工具类）去实现。其实就是子类把要增加的代码写在beforeMethod和afterMethod方法里。这两个方法后文的代码截图会提到。
4. 通过`ByteBuddy`API在字节码加载时修改字节码，实现增强字节码。具体增强代码见`org.apache.skywalking.apm.agent.core.plugin.interceptor.enhance.v2.ClassEnhancePluginDefineV2#enhanceClass`方法。

为什么字节码加载时能修改？谁通知`ByteBuddy`修改？

这个功能由`JVM`提供的`Instrumentation`接口实现  
这个接口是用于类加载时对其字节码进行修改。修改的内容就是增加我们定义的BeforeMethod方法和AfterMethod方法，如图4中展示的BeforeMethod方法  
从Java 7开始，这个接口可以在运行时重新定义已加载的类（如果字节码已经加载过了，那么就不能改变其结构，如添加或移除字段或方法）。这样可以在不重启应用的情况下更新某些行为，对于调试和热修复非常有用。


```java
agentBuilder.type(pluginFinder.buildMatch())
                    .transform(new Transformer(pluginFinder))
                    .with(AgentBuilder.RedefinitionStrategy.RETRANSFORMATION)
                    .with(new RedefinitionListener())
                    .with(new Listener())
                    .installOn(instrumentation);//注册instrumentation接口
```

<h3 id="gAxNk">链路追踪，如何实现？</h3>
一个segment里面有多个span。每个span代表一个操作。

span分为entryspan,localspan,exitspan。entryspan只能有一个。

每个RPC操作（或其它服务）创建span时都会默认创建entryspan。同时用一个栈维护这些span。此外还有两个字段记录当前栈深和历史最大栈深。如果历史最大栈深大于1，说明entryspan已经被创建了，那么就创建localspan。

<h4 id="MG5oe">同步</h4>
记录当前节点里的链路的TracingContext类里有一个栈，保存在该节点一次请求中发生的span。tracingcontext对象被放进了ThreadLocal。每次创建span时需要通过getOrCreate方法获取tracingcontext对象，然后将生成的span放进这个对象保存span的栈里面（通过LinkedList模拟栈）。

![图1，TraceContext是ThreadLocal类型](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img.png)


当前节点的流程结束后，即栈的深度为 0，会调用ThreadLocal的remove方法把本次流程的span数据全部清空

![图2，将 span 弹出栈。如果栈的深度为 0，isEmpty，返回 true](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_1.png)


![图3，若图2方法返回 true，则清空本线程的ThreadLocal类型的Context](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_2.png)




<h5 id="l3PGB">举例，对Dubbo类型的 span 出入栈</h5>

![图4，对Dubbo的插桩实现](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_3.png)


上图中的beforeMethod方法就是对dubbo插桩的代码。不同的中间件有不同的插桩实现。

上图中line76调用下图中的createExitSpan方法。return push方法的返回值。push方法正是将生成的span压入栈内。

![图5，将生成的span压入栈内](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_4.png)



![图6，在afterMehtod插桩方法内，调用图二的 stopSpan 方法，将span弹出栈](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_5.png)



一个问题：像下面的代码：

```java
@Dubbo
RPCService rpcService;

public Res rpcFunc(int sign) {
    Res result1 = rpcService.rpcFunc1(sign);
    Res result2 = rpcService.rpcFunc2(sign);
    return result1;
}
```

执行`rpcFunc`方法时创建了一个`TracingContext`。怎么保证执行`rpcFunc1`和`rpcFunc2`方法不会再次创建一个新的`TracingContext`呢？

由`ThreadLocal`解决。

只要执行`rpcFunc1`和`rpcFunc2`的方法和执行`rpcFunc`的方法在一个线程里，它们关联到的`TracingContext`就是同一个。

但是异步调用怎么办？

<h4 id="eOPk3">异步</h4>
```java
@Dubbo
RPCService rpcService;

public Res rpcFunc(int sign) {
    Runnable rpcTask = () -> rpcService.rpcFunc1(sign);
    CompletableFuture<Res> future = CompletableFuture.supplyAsync(rpcTask1);
    return future.get();
}
```

别的线程怎么能知道它有没有链路上文呢？



把Trace 数据发给中间人，新线程从中间人获取。

再怎么跨线程也是在JVM内，也是通过创建Thread来跨线程。那就对JDK里面的Thread库也插桩，拦截Thread的构造方法，把数据打成快照发给中间人。创建线程后从中间人拿快照数据。这样就实现了跨线程的传递数据。

至于如何保证传递数据的准确性，就是另一回事了。

![图7，拦截线程的构造方法](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_6.png)


ContextManager.capture()方法就是专门用于跨线程传递数据，将TraceID等数据打成快照，通过objInst.setSkyWalkingDynamicField方法传递给下一个线程。

从这个方法的实现来看，是把快照发给Kafka或者ES。

![图8，EnhanceInstance接口的实现类](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_7.png)


![图9，老线程创建快照](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_8.png)



![图10，新线程获取快照](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_9.png)


这是JDK插件模块里的ThreadingMethodInterceptor类，顾名思义，对线程方法的拦截。拦截点是`org.apache.skywalking.apm.plugin.jdk.threading.ThreadingConstructorInterceptor` 

在该方法执行前，通过getSkyWalkingDynamicField方法拿到Trace数据的快照（实现类只有kafka插件模块和ES插件模块里有）

再通过ContextManager.continued方法把快照恢复到ThreadLocal类型的Context变量里。



完了吗？



一个很重要的细节还没提到。

上文提到的线程拦截会拦截实现了 Callable 和 Runable 接口的任何线程

假设一个场景：

A线程接收到RPC请求，创建B线程异步调用别的服务。与此同时，A线程所在的节点还创建了一批线程处理别的非链路任务。难道这些链路无关的线程也要被拦截去执行BeforeMethod方法？这显然是不合理的。

怎么判断一个线程是否由链路上的线程创建？或者说：SkyWalking怎么控制线程插桩的粒度？



<h4 id="Wo0oP">控制对线程/线程池插桩的粒度</h4>
待续，本文会持续更新。

具体代码在`apm-sniffer/bootstrap-plugins/jdk-threading-plugin`和`apm-sniffer/bootstrap-plugins/jdk-threadpool-plugin`模块里。这是对线程和线程池插桩的实现。

 



<h4 id="itPj1">跨进程时Trace数据怎么传递？</h4>
skywalking将span分为了三种类型。EntrySpan/LocalSpan/ExitSpan。任何跨进程的操作都会生成ExitSpan。

创建ExitSpan时调用inject 方法

![图11，跨进程，发送carrier](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_10.png)


![图12，将Trace数据包装成ContextCarrier对象，通过DataCarrier发给下一个节点](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_11.png)


至于链路数据的存储和发送，则是通过`org/apache/skywalking/apm/agent/core/remote/TraceSegmentServiceClient.java`类实现存储， DataCarrier 模块实现发送

![图13，DataCarrier模块](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-12-20-SkyWalking原理概述/img_12.png)


这是 SkyWalking 自己实现的数据发送方式

默认通过 GRPC 向它自己的后端 OAP发送

从6.1.0 版本开始，也支持通过 Kafka 发送





<h3 id="EF4c4">如何在 RPC 框架内部实现RPC链路追踪？</h3>

**对于同步调用**  

在RPC报文字段里添加traceID和SegmentID等字段，B服务的 X 方法收到A服务的调用时，解析出TraceID和SegmentID，将TraceID放在ThreadLocal里面的TraceContext里，SegmentID赋值给parentID。

执行过程中如果**同步调用**了其它RPC请求，那么这些请求都去ThreadLocal里拿到TraceID，如果拿不到说明它是本段链路的起点。同时记录本次RPC调用的信息（TraceID，OperationName，SegmentID，SpanID，CreateTime，ParentID等等。

同时用一个队列记录本节点 RPC 调用情况。B服务收到A服务的调用时，入队列。

队列也要保存在 ThreadLocal 里。通过 Netty 发起 RPC 时入队列。

Method.invoke 方法执行 X 方法结束后，本节点的 Trace 结束， 将队列元素全部弹出至 MySQL。

后续查看链路信息从MySQL中统计即可。

**如何感知本节点内的链路结束并清除ThreadLocal呢？** 
执行RPC方法用的是Method类的invoke方法，在invoke方法结束后清除threadlocal即可。不用担心这两个步骤不是原子执行会导致下一次RPC链路使用本线程上一个链路的ThreadLocal



**对于异步调用**

实现起来比同步调用更难一些，除了显式地在形参里添加 Trace 参数，我能想到的唯一办法就是像 SkyWalking 一样对 Thread 库插桩。

