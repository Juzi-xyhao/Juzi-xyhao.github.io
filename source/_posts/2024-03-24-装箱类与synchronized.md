---
title: 装箱类
tags:
  - JUC
  - Java
  - Synchronized
categories: [Java,其它]
author: xyhao
keywords: 装箱类缓存了一些数据，这些数据只有一个内存地址
description: 装箱类缓存了一些数据，这些数据只有一个内存地址
top_img: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/articleCover/2024-03-24-lock.png
cover: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/articleCover/2024-03-24-lock.png
abbrlink: bdd01c69
date: 2024-03-24 00:00:00
---

<br>

```java
package org.Solution.Algorithm;

import java.util.concurrent.atomic.AtomicInteger;

public class Third {
    private static Integer i = 0;
    private static AtomicInteger atomicI = new AtomicInteger(0);

    public static void main(String[] args) throws InterruptedException {
        // 创建两个线程并启动
        Thread unsafeThread = new Thread(() -> {
            for (int j = 0; j < 100; j++) {
                synchronized (i){
                    i++;
                }
            }
        });
        Thread unsafeThread1 = new Thread(() -> {
            for (int j = 0; j < 100; j++) {
                synchronized (i){
                    i--;
                }
            }
        });

        unsafeThread.start();
        unsafeThread1.start();

        // 等待两个线程运行结束
        unsafeThread.join();
        unsafeThread1.join();

        // 输出最终的结果
        Thread.sleep(1000);
        System.out.println("Unsafe i: " + i);
    }
}
```
当循环次数在127以内时，每次执行完毕i一定是0，这是由synchronized保证的。<br />但是循环次数大于127呢？<br />
i是一个Integer对象。在Java中，自动装箱的Integer对象在作为同步锁时，由于其值可能在内存中不唯一（因为Integer缓存了-128到127之间的值，超出这个范围的值才会每次创建新的对象），
可能导致意料之外的同步行为。

附上两个运行结果：

![img.png](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-03-24-Integer&synchronized/img.png)
![img_1.png](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-03-24-Integer&synchronized/img_1.png)


