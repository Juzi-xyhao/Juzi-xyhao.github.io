---
title: Java里两种执行命令的方式比较
tags:
  - 命令
  - Java
categories: [Java,其它,Java里两种执行命令的方式比较]
author: xyhao
keywords: ProcessBuilder VS Runtime.exec()
description: ProcessBuilder VS Runtime.exec()
top_img: >-
  https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleCover/2024-03-09-ProcessBuilder.png
cover: >-
  https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleCover/2024-03-09-ProcessBuilder.png
abbrlink: c56a813c
date: 2024-03-09 00:00:00
---
> 更多博客请见 [我的语雀知识库](https://www.yuque.com/u41117719/xd1qgc)

<br>

> 我的网盘程序部署在服务器上，前端资源通过nginx托管。但不知为何，nginx总是每隔几天就被kill了。所以我在后台程序内部搞了一个定时任务<br>
> 每隔一段时间重启nginx。执行重启命令使用了Runtime.exec方法。但后来在实习过程中发现公司的项目里执行命令行命令使用了ProcessBuilder。<br>
> 于是我研究（GPT）了一下两者的区别，并写下这篇笔记。

Runtime.getRuntime().exec(cmd); 和使用 ProcessBuilder 来创建并启动进程之间有几个主要的区别：
1. 参数处理
   1. Runtime.exec(String cmd) 方法接受一个单一的字符串参数，这个字符串应该是一个完整的命令行，包括所有的参数和必要的分隔符（在Windows上是空格，在Unix/Linux上通常是空格和引号）。这意味着你必须自己处理所有参数的拼接和转义，这可能会导致一些难以察觉的错误和安全问题（如命令注入攻击）。
   2. ProcessBuilder 允许你以更结构化的方式设置命令和参数。你可以将命令和每个参数作为单独的字符串传递给 ProcessBuilder 的构造函数或 command 方法。ProcessBuilder 会自动处理这些参数，使得代码更清晰、更安全。

2. 错误流处理：
   1. 使用 Runtime.exec 时，默认情况下标准输出流（stdout）和标准错误流（stderr）是分开的。你需要单独处理这两个流，否则可能会丢失错误信息或导致程序挂起。
   2. ProcessBuilder 允许你通过 redirectErrorStream(true) 方法将 stderr 重定向到 stdout，从而简化输出处理。
3.  环境变量和工作目录：
    1. ProcessBuilder 提供了更多的配置选项，如设置环境变量（通过 environment() 方法）和工作目录（通过 directory() 方法）。而 Runtime.exec 提供的配置选项较少。
4.  线程安全性：
    1. ProcessBuilder 是线程安全的，而 Runtime.exec 不是。如果你在多线程环境中使用 Runtime.exec，需要格外小心以避免潜在的问题。
5.  资源管理：
    1. ProcessBuilder 返回的 Process 对象提供了更多关于子进程状态的信息，比如是否活着（通过 isAlive() 方法）以及等待进程结束并获取退出值（通过 waitFor() 方法）。 
    2. 使用 Runtime.exec 时，你也需要手动管理子进程的输入/输出流，并确保它们在使用后被正确关闭，以避免资源泄漏。

6. 异常处理：
   1. ProcessBuilder 的 start() 方法不会抛出 IOException，但是返回的 Process 对象的 waitFor() 方法会抛出。这使得错误处理更加明确。
   2. Runtime.exec 直接抛出 IOException，这可能需要更多的异常处理代码。
   
总的来说，ProcessBuilder 提供了更灵活、更安全、更易于管理的进程创建和配置选项。因此，在现代Java编程中，通常推荐使用 ProcessBuilder 而不是 Runtime.exec 来创建和启动进程。
