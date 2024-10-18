---
title: synchronized底层
tags:
  - JUC
  - Java
  - Synchronized
categories: Java
author: xyhao
keywords: 锁升级的过程
description: 锁升级的过程
top_img: >-
  https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleCover/2024-04-05-synchronized.png
cover: >-
  https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleCover/2024-04-05-synchronized.png
abbrlink: 5e93ca9c
date: 2024-04-05 00:00:00
---
> 更多博客请见 [我的语雀知识库](https://www.yuque.com/u41117719/xd1qgc)

<br>

synchronized可以修饰方法、静态方法、代码块。修饰方法和静态方法时，方法的字节码文件中会多一个标识：ACC_SYNCHRONIZED。
当调用设置了 ACC_SYNCHRONIZED 的方法时，执行线程进入监视器（monitor），然后执行这个方法，方法执行完毕后退出监视器。需要注意的是，无论这个方法是正常完成还是突然完成，在执行线程拥有监视器期间，没有其他线程可以进入这个方法。



## 关于monitor
上文我们总是把 monitor 翻译为监视器，其实各位如果系统地学习过操作系统，对 monitor 一定不陌生，它也被翻译为管程。常见的进程同步与互斥机制就是信号量和管程，相比起信号量，管程有一个重要特性：在一个时刻只能有一个进程使用管程，即进程在无法继续执行的时候不能一直占用管程，否则其它进程将永远不能使用管程。也就是说管程天生支持进程互斥。
其实使用管程是能够实现信号量的，并且也能用信号量实现管程。但是管程封装的比较好，相比起信号量来需要我们编写的代码更少，更加易用。
把管程翻译为 Java 领域的语言，就是管理类的成员变量和成员方法，让这个类是线程安全的。
而对象和monitor是一一对应的	
## monitorenter
执行 monitorenter 的线程会尝试获得监视器的所有权，或者说尝试获得对象的锁（反过来说就是不加 synchronized 的对象是不会被锁住的）。
另外，每个监视器都维护着一个自己被持有次数的计数器，具体如下：
如果与对象关联的监视器的计数器为零，则线程进入监视器成为该监视器的拥有者，并将计数器设置为 1。
当同一个线程再次进入该对象的监视器的时候，计数器会再次自增(这也说明了synchronized是可重入锁)。
当其他线程想获得该对象关联的监视器的时候，就会被阻塞住，直到该监视器的计数器为 0 才会再次尝试获得其所有权
## 关于monitorexit
某个线程想要执行 monitorexit 指令，那它一定得是某个监视器的拥有者才行。
当某个线程执行 monitorexit 指令的时候，该线程拥有的监视器的计数器就会减一。如果计数器为 0，就表明该线程不再拥有监视器了，这样，其他线程就可以去尝试获得这个监视器了。

当synchronized修饰代码块时，代码块所处的那个方法的字节码中会多出两个指令 monitorenter 和 monitorexit，也就是说在同步方法块中，JVM 使用 monitorenter 和 monitorexit 这两个指令实现同步。
## 锁是如何升级的呢？
![](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-04-05-synchonized/img.png)

锁标志位 “01” + 是否是偏向锁 “0” 表示无锁状态，也就是说该对象没有被锁定
锁标志位 “01” + 是否是偏向锁 “1” 表示偏向锁状态

### 轻量级锁加锁的过程是这样的：

1. Mark Word 的初始状态：在代码即将进入同步块的时候，如果此同步对象没有被锁定，也即 Mark Word 中的锁标志位 “01” + 是否是偏向锁 “0”：

![](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-04-05-synchonized/img_1.png)

2. 在当前线程的栈帧中建立一个锁记录：Java 虚拟机会在将在当前线程的栈帧中建立一个名为 锁记录（Lock Record） 的空间，Lock Record 中有一个字段 displaced_header，用于后续存储锁对象的 Mark Word 的拷贝：

![](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-04-05-synchonized/img_2.png)

3. 复制锁对象的 Mark Word 到锁记录中：把锁对象的 Mark Word 复制到锁记录中，更具体来讲，是将 Mark Word 放到锁记录的 displaced_header 属性中。官方给这个复制过来的记录起名 Displaced Mark Word：

![](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-04-05-synchonized/img_3.png)

4. 使用 CAS 操作更新锁对象的 Mark Word。Java 虚拟机使用 CAS 操作尝试把锁对象的 Mark Word 更新为指向锁记录的指针，并将锁记录里的 owner 指针指向对象的 Mark Word。如果这个更新操作成功了，就表明获取轻量级锁成功，也就是说该线程拥有了这个对象的锁！并且该对象 Mark Word 的锁标志位会被改为 00，即表示此对象处于轻量级锁定状态。如果这个更新操作失败了，那有两种可能性：
   1. 当前线程已经拥有了这个对象锁（直接进入同步块继续执行）
   2. 存在其他的线程竞争获取这个对象锁（膨胀成重量级锁，锁标志的状态值变为 10，Mark Word 中存储的就是指向重量级锁（互斥量）的指针

为了证实到底是哪种情况，虚拟机首先会检查该对象的 Mark Word 是否指向当前线程的栈帧，如果是就说明当前线程已经拥有了这个对象的锁，那就可以直接进入同步块继续执行（synchronized 是可重入锁）。

假设锁的状态是轻量级锁，下图反应了对象的 Mark word 和线程栈中锁记录的状态，可以看到左边线程栈中包含3个指向当前锁对象的 Lock Record。其中栈中最高位的锁记录为第一次获取轻量级锁时分配的，其 Displaced Mark word 的值为锁对象 obj 加锁之前的 Mark word，之后的每次锁重入都会在线程栈中分配一个 Displaced Mark word 为 null 的锁记录。
![](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-04-05-synchonized/img_4.png)
那么问题来了，为什么 synchronized 重入的时候 Java 虚拟机要在线程栈中添加 Displaced Mark word 为 null 的锁记录呢？
首先锁重入次数是一定要记录下来的，因为每次解锁都需要对应一次加锁，只有解锁次数等于加锁次数时，该锁才真正的被释放，也就是在解锁时需要用到说锁的重入次数。
最简单的记录锁重入次数的方案就是将其记录在对象头的 Mark word 中，但 Mark word 大小有限，没有多出来的地方存放该信息了。另一个方案就是在锁纪录中记录重入次数，但这样做的话，每次重入获得锁的时候都需要遍历该线程的栈找到对应的锁纪录，然后去修改重入次数的值，显然这样效率不是很高。
所以最终 Hotspot 选择了每次重入获得锁都添加一个锁记录来表示锁的重入，这样有几个 Displaced Mark word 为 null 的锁记录就表示发生了几次锁重入，非常简单。
以上，就是 synchronized 锁重入的原理。


再来看 CAS 更新操作失败的第二种情况，如果这个更新操作失败了并且该对象的 Mark Word 并没有指向当前线程的栈帧，就说明多个线程竞争锁。注意！！！这里就是我说的《Java 并发编程的艺术》书中出现错误的地方，我们来看原文
> 线程在执行同步块之前，JVM 会先在当前线程的栈桢中创建用于存储锁记录的空间，并将对象头中的 Mark Word 复制到锁记录中，官方称为 Displaced Mark Word。然后线程尝试使用 CAS 将对象头中的 Mark Word 替换为指向锁记录的指针。如果成功，当前线程获得锁，<u>如果失败，表示其他线程竞争锁，当前线程便尝试使用自旋来获取锁。</u>
> 

![](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-04-05-synchonized/img_5.png)
看上方划线的句子，话不多说，我们接着上面那段源码往下看：
可以看到并没有什么自旋操作，如果 CAS 成功就直接 return 了，如果失败就会执行下面的锁膨胀方法 ObjectSynchronizer::inflate，这里面同样也没有自旋操作。
**注意，从这段源码可以看到，锁的升级是用C++方法实现的**
所以从源码来看轻量级锁 CAS 失败（存在其他的线程竞争获取这个对象锁的情况）并不会自旋而是直接膨胀成重量级锁。

## 关于对象头
我们上述讲到的所有底层原理，其实都在这句话的基础之上：Each object is associated with a monitor
那么，一个对象和一个 monitor 是如何关联起来的呢？
在HotSpot虚拟机里，对象在堆内存中的存储布局可以划分为三个部分：对象头（Header）、实例数据（Instance Data）和对齐填充（Padding）。
其中，如果对象是数组类型，则虚拟机用 3 个字宽（Word）存储对象头（Mard Word、类型指针、数组长度），如果对象是非数组类型，则用 2 字宽存储对象头（Mard Word、类型指针）。在 32 位虚拟机中，1 字宽等于 4 字节，即 32 bit，如表所示：
![](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-04-05-synchonized/img_6.png)
![img.png](https://raw.githubusercontent.com/Juzi-xyhao/Juzi-xyhao.github.io/master/assets/articleSource/2024-04-05-synchonized/img_7.png)
Mark Word 就是对象与 monitor 关联的重点所在！ 《深入理解 Java 虚拟机 - 第 3 版》中是这样描述 Mark Word 的：
> HotSpot 虚拟机对象的对象头部分包括两类信息。第一类是用于存储对象自身的运行时数据，如哈希码（HashCode）、GC 分代年龄、锁状态标志、线程持有的锁、偏向线程 ID、偏向时间戳等，这部分数据的长度在 32 位和 64 位的虚拟机（未开启压缩指针）中分别为 32 个比特和 64 个比特，官方称它为 “Mark Word”。
> 对象需要存储的运行时数据很多，其实已经超出了 32、64 位 Bitmap 结构所能记录的最大限度，但对象头里的信息是与对象自身定义的数据无关的额外存储成本，考虑到虚拟机的空间效率，Mark Word 被设计成一个有着动态定义的数据结构，以便在极小的空间内存储尽量多的数据，根据对象的状态复用自己的存储空间。


> 参考：[力扣](https://leetcode.cn/leetbook/read/concurrency/aty716/)



TODO  JDK21有对对象头的瘦身	
