---
title: GraalVM 静态编译下 OTel Java Agent 的自动增强方案与实现
tags:
  - JVM
  - Java
categories: [Java,编译,GraalVM 静态编译下 OTel Java Agent 的自动增强方案与实现]
author: xyhao
keywords: 静态编译导致Java程序很多特性都失效了
description: 静态编译导致Java程序很多特性都失效了
top_img: >-
  https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleCover/2024-07-14-GraalVM.png
cover: >-
  https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleCover/2024-07-14-GraalVM.png
copyright_author: 阿里巴巴中间件
copyright_url: 'https://mp.weixin.qq.com/s/kEqBut3gcV9RM86DAMJLRA'
abbrlink: 1105307b
date: 2024-07-14 00:00:00
copyright_author_href:
copyright_info:
---

> 这篇文档的创作灵感来源于阿里巴巴中间件微信公众号的推文，是对其的解读  
> [GraalVM 静态编译下 OTel Java Agent 的自动增强方案与实现](https://mp.weixin.qq.com/s/kEqBut3gcV9RM86DAMJLRA)  
> 本文档讨论的动态、静态编译仅限于java语言  
> 更多博客请见 [我的语雀知识库](https://www.yuque.com/u41117719/xd1qgc)

## 什么是动态编译？
启动jar运行程序时，热点代码会被JVM以JIT（Just-In-Time Compilation,即时编译）的形式编译为机器码。当我们启动jar包时，实质上是启动了一个JVM，然后执行类加载，JIT将热点字节码编译为机器码这三个部分。

也就是说，**java的动态编译是指动态地将热点字节码编译为机器码直接让CPU执行。**

> 需要注意的是，类加**载这个过程**实际上在启动阶段只会加载那些需要被运行的类。笔者在起草这篇文档时已经很久没有接触过JVM的八股了，**忘了类加载的时机**，**以为所有的类在启动时都会被加载**。导致没有理解后续的JIT编译热点代码。[类的生命周期与加载时机](https://www.yuque.com/u41117719/xd1qgc/iqfmoe9tpnstvw0i)
> **明明所有的类都被加载了,为什么还有编译为机器码的步骤？**
> 这是笔者的第二个误区。类的字节码被加载进JVM内存后，JVM会将字节码解析并转换为JVM内部的数据结构，比如:
> - **方法区,**记录类的相关信息：类名、方法、变量等等
> - **虚拟机栈**，用栈帧记录每个java方法从调用直至执行完成的过程。栈帧中存储了局部变量表、操作数栈、动态链接、方法返回地址等等信息
> - **本地方法栈**：与虚拟机栈几乎完全相同。区别在于本地方法栈如其名，只记录native的C++方法
> - **堆**：存储对象实例和**数组**。是的，也有数组。java秉持着**一切皆对象**的原则，大方地让数组，甚至基本数据类型都继承了Object类。
> - **运行时常量池**：存储像符号引用(类和接口的全限定名、字段名称、方法名称)、编译期计算出来的常量表达式、字符串常量、枚举类常量等等。

[运行时内存区域](https://www.yuque.com/u41117719/xd1qgc/hreiiqh4texe9z9m)
> 字节码在JVM里并不是以机器码执行的。能够执行机器码的，只有CPU。
> 只是说频繁被使用的字节码会由JIT编译为字节码**直接**让CPU去执行，提高执行效率。
> 秋招前夕，笔者的JVM已经忘得差不多了，难绷


## 什么是静态编译？
相比于动态编译只将热点数据编译为机器码让CPU执行，静态编译是把所有字节码全部编译为机器码并打包为二进制可执行文件（如Windows平台的exe文件）。
不过由于不同操作系统的二进制文件格式并不一样, 所以静态编译时需要程序员手动指定操作系统


## 静态编译有哪些问题？
下文基于文档开头提到的公众号文章中提到的静态编译技术：GraalVM的Native Image。
以下三点问题均引用自公众号原文。
## “一次编译，处处运行”失效了
以往依托于字节码和JVM，确实可以处处运行。但是静态编译只是把字节码作为中间变量，是生成二进制可执行文件的中间工具。为windows平台编译的exe可执行文件没办法在mac和linux上接着执行。

## java的许多动态特性都不直接生效了
例如动态类加载，反射，动态代理等。

- 动态类加载失效：Native Image在构建时就需要知道应用会用到的所有类，然后把这些类打包进二进制文件。这样在运行时就不需要再加载任何类了，因为所有需要的类都已经在里面了。
- 反射失效：java的反射的原理是根据类的字节码获取类的信息。而在静态编译中，编译期就要把代码全部编译完，且不会保留任何类的元数据。程序运行时动态的反射指定的类对静态编译而言是不知道的。这就会导致即使字节码存在，元数据的丢失也会导致反射失效。<br>因为反射就是通过类的元数据加载这个类的方法和字段的。所以需要手动指定哪些类会被反射，静态编译才会把它们的元数据和字节码编译进最终生成的二进制文件中
- 动态代理失效：不管JDK代理还是CGLIB代理，都是基于原有字节码创建新的字节码。而在静态编译中，由于没有了字节码和元数据的概念，动态代理自然就和反射一样失效了。

> ###### 为什么静态编译会丢失元数据？
> 待补充

## 基于字节码改写实现的Java Agent将不再适用
因为没有了字节码概念，所以之前我们通过 Java Agent 做到的各种可观测能力，例如收集 Trace/Metrics 等信号这些能力都不能生效了。


总的来说，静态编译导致的字节码缺失是java程序的许多特性都失效的根本原因。

## 如何解决静态编译带来的问题？
参考原文第二部分：![image.png](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-07-14-GraalVM/img.png)

![image.png](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-07-14-GraalVM/img_1.png)
![image.png](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-07-14-GraalVM/img_2.png)
![image.png](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-07-14-GraalVM/img_3.png)


总的来说，是通过在native编译前先用普通的jvm执行一遍，把需要修改和增强的扩展点识别出来保存下来，然后native编译的时候再基于这些东西去增强。

对于加载过程之前的字节码修改可以前置到编译时期，对运行时的，像arthas，又该如何解决呢？
