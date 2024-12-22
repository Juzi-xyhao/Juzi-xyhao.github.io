---
title: ConcurrentHashMap并发扩容
tags:
  - HashMap
  - Java
categories: [Java,HashMap]
author: xyhao
keywords: JDK8使用细粒度更高的cas并发扩容
description: JDK8使用细粒度更高的cas并发扩容
top_img: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/articleCover/ConcurrentHashMap.png
cover: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/articleCover/ConcurrentHashMap.png
abbrlink: fa7a6888
date: 2024-08-27 00:00:00
---


> 更多细节见[ConcurrentHashMap 源码分析](https://javaguide.cn/java/collection/concurrent-hash-map-source-code.html#_3-put)


JDK7和JDK8两个版本的扩容有点不一样。
# JDK7
JDK7版本中，扩容是在持有锁时发生的。
![](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-08-27-concurrentHashMap/img_4.png)
35行的rehash是扩容函数。直到46行的finally代码块才释放锁。  
拿到锁的线程执行put方法时会检查要不要扩容（已有元素个数 / table数组的长度  > 负载因子）。  
因此只有一个线程可以执行扩容操作，不存在并发问题。  
但是map扩容了总得让其它线程知道吧。具体是怎么知道的呢？  
其实数组table是一个volatile变量，这就保证了可见性。  
证据见JDK 8中源码778行。我没有装JDK 7,但JDK7里也肯定是一个volatile变量。  
![](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-08-27-concurrentHashMap/img.png)



# JDK8
JDK8版本中，扩容是在不持有锁时发生的。  
![](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-08-27-concurrentHashMap/img_1.png)  
倒数第三行的addCount是扩容的检查函数，可以清晰的看到，它不在syncronized代码块里。  

先看看add方法：  
![](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-08-27-concurrentHashMap/img_2.png)   
**扩容检查流程：**

- 计算元素总量 size，若 CAS 冲突严重则放弃扩容。  
- 若 size 计算成功，有新元素加入，且检测到元素总量大于阈值 size > sizeCtl。  
   - 如果检查到当前已有线程在进行扩容。  
      - 扩容已经接近完成或足够多的线程参与到扩容中了，当前线程直接返回。  
      - 当前线程参与扩容。  
   - 如果没有其他线程在进行扩容，则修改 sizeCtl 标识，进行扩容。  

## 扩容流程
上述流程只是扩容之前的准备，扩容的核心逻辑在 transfer() 方法中。  
### transfer() 源码
看源码之前，提前梳理一下扩容过程：  

1. 创建 nextTable，新容量是旧容量的 2 倍。  
2. 将原 table 的所有桶逆序分配给多个线程，每个线程每次最小分配 16 个桶，防止资源竞争导致的效率下降。指定范围的桶可能分配给多个线程同时处理。  
3. **扩容时遇到空的桶，采用 CAS 设置为 ForwardingNode 节点，表示该桶扩容完成。**  
4. **扩容时遇到 ForwardingNode 节点，表示该桶已扩容过了，直接跳过。**  
5. **单个桶内元素的迁移是加锁的**，将旧 table 的 i 位置上所有元素迁移到新表。  
6. 最后将旧 table 的 i 位置设置为 ForwardingNode 节点。  
7. 所有桶扩容完毕，将 table 指向 nextTable，设置 sizeCtl 为新容量 0.75 倍    


```java
private final void transfer(Node<K,V>[] tab, Node<K,V>[] nextTab) {
    int n = tab.length, stride;
    if ((stride = (NCPU > 1) ? (n >>> 3) / NCPU : n) < MIN_TRANSFER_STRIDE) // 每核处理的桶的数目，最小为16
        stride = MIN_TRANSFER_STRIDE; // MIN_TRANSFER_STRIDE写死了16，每个线程每次只分配16个桶
    if (nextTab == null) {            // initiating
        try {
            @SuppressWarnings("unchecked")
            Node<K,V>[] nt = (Node<K,V>[])new Node<?,?>[n << 1]; // 构建nextTable，其容量为原来容量的两倍
            nextTab = nt;
        } catch (Throwable ex) {      // try to cope with OOME
            sizeCtl = Integer.MAX_VALUE;
            return;
        }
        nextTable = nextTab;
        transferIndex = n; // 迁移总进度，值范围为[0,n]，表示从table的第n-1位开始处理直到第0位。
    }
    int nextn = nextTab.length;
    ForwardingNode<K,V> fwd = new ForwardingNode<K,V>(nextTab); // 扩容时的特殊节点，hash固定为-1，标明此节点正在进行迁移。扩容期间的元素查找要调用其find方法在nextTable中查找元素
    boolean advance = true; // 当前线程是否需要继续寻找下一个可处理的节点
    boolean finishing = false; // to ensure sweep before committing nextTab // 所有桶是否都已迁移完成
    for (int i = 0, bound = 0;;) {
        Node<K,V> f; int fh;
        while (advance) { // 此循环的作用是 1.确定当前线程要迁移的桶的范围；2.通过更新i的值确定当前范围内下一个要处理的节点
            int nextIndex, nextBound;
            if (--i >= bound || finishing) // 每次循环都检查结束条件：i自减没有超过下界，finishing标识为true时，跳出while循环
                advance = false;
            else if ((nextIndex = transferIndex) <= 0) { // 迁移总进度<=0，表示所有桶都已迁移完成
                i = -1;
                advance = false;
            }
                 /*
                    下面这段代码通过cas的方式确定自己负责的桶范围。
                    假如有多个线程都执行到了下面这行代码，
                    怎么保证只有一个线程可以cas成功？
                    或者说，32-16的桶范围只有一个线程可以拿到？
                    U是一个unsafe对象，可以直接操作内存
                    TRANSFERINDEX通过U这个unsafe对象获取了transferIndex的内存地址，
                    修改TRANSFERINDEX就等于直接修改transferIndex
                    而transferIndex是一个volatile变量
                    每个线程在TRANSFERINDEX=nextIndex时都会发出写屏障修改TRANSFERINDEX
                    但是CPU的总线仲裁机制能够保证：
                    只有一个线程可以发出写屏障更新TRANSFERINDEX(transferIndex)
                    并且向CPU总线发出广播，让其它核心（线程）的缓存块失效
                    等它们从主内存更新缓存块后，cas的条件已经不成立了。于是陷入自旋
                    自旋超时后，会返回false，执行后面的代码。
                    可能这时已经扩容完了没它事。
                    竞争失败后就相当于走了个过场。
                */
            else if (U.compareAndSwapInt
                     (this, TRANSFERINDEX, nextIndex,
                      nextBound = (nextIndex > stride ?
                                   nextIndex - stride : 0))) { // CAS执行transferIndex=transferIndex-stride，即transferIndex减去已分配出去的桶，得到边界，这里为下界
                bound = nextBound; // 当前线程需要处理的桶下标的下界
                i = nextIndex - 1; // 当前线程需要处理的桶下标
                advance = false;
            }
        }
        if (i < 0 || i >= n || i + n >= nextn) { // 当前线程自己的活已经做完或所有线程的活都已做完
            int sc;
            if (finishing) { // 已经完成所有节点复制了。所有线程已干完活，最后才走这里
                nextTable = null;
                table = nextTab; // table指向nextTable
                sizeCtl = (n << 1) - (n >>> 1); // 设置sizeCtl为新容量0.75倍
                return;
            }
            if (U.compareAndSwapInt(this, SIZECTL, sc = sizeCtl, sc - 1)) { // 当前线程已结束扩容，sizeCtl-1表示参与扩容线程数-1
                if ((sc - 2) != resizeStamp(n) << RESIZE_STAMP_SHIFT) // 相等时说明没有线程在参与扩容了，置finishing=advance=true，为保险让i=n再检查一次
                    return;
                finishing = advance = true;
                i = n; // recheck before commit
            }
        }
        else if ((f = tabAt(tab, i)) == null) // 遍历到i位置为null，则放入ForwardingNode节点，标志该桶扩容完成。
            advance = casTabAt(tab, i, null, fwd);
        else if ((fh = f.hash) == MOVED) // f.hash == -1 表示遍历到了ForwardingNode节点，意味着该节点已经处理过了
            advance = true; // already processed
        else {
            synchronized (f) { // 桶内元素迁移需要加锁
                if (tabAt(tab, i) == f) {
                    Node<K,V> ln, hn;
                    if (fh >= 0) { // 链表节点。非链表节点hash值小于0
                        int runBit = fh & n; // 根据 hash&n 的结果，将所有结点分为两部分
                        Node<K,V> lastRun = f;
                        for (Node<K,V> p = f.next; p != null; p = p.next) {
                            int b = p.hash & n; // 遍历链表的每个节点，依次计算 hash&n
                            if (b != runBit) {
                                runBit = b;
                                lastRun = p;
                            }
                        }
                        if (runBit == 0) {
                            ln = lastRun;
                            hn = null;
                        }
                        else {
                            hn = lastRun;
                            ln = null;
                        }
                        for (Node<K,V> p = f; p != lastRun; p = p.next) {
                            int ph = p.hash; K pk = p.key; V pv = p.val;
                            if ((ph & n) == 0)
                                ln = new Node<K,V>(ph, pk, pv, ln); // hash&n为0，索引位置不变，作低位链表
                            else
                                hn = new Node<K,V>(ph, pk, pv, hn); // hash&n不为0，索引变成“原索引+oldCap”，作高位链表
                        }
                        setTabAt(nextTab, i, ln); // 低位链表放在i处
                        setTabAt(nextTab, i + n, hn); // 高位链表放在i+n处
                        setTabAt(tab, i, fwd); // 在原table的i位置设置ForwardingNode节点，以提示该桶扩容完成
                        advance = true;
                    }
                    else if (f instanceof TreeBin) {
                        TreeBin<K,V> t = (TreeBin<K,V>)f;
                        TreeNode<K,V> lo = null, loTail = null;
                        TreeNode<K,V> hi = null, hiTail = null;
                        int lc = 0, hc = 0;
                        for (Node<K,V> e = t.first; e != null; e = e.next) {
                            int h = e.hash;
                            TreeNode<K,V> p = new TreeNode<K,V>
                                (h, e.key, e.val, null, null);
                            if ((h & n) == 0) {
                                if ((p.prev = loTail) == null)
                                    lo = p;
                                else
                                    loTail.next = p;
                                loTail = p;
                                ++lc;
                            }
                            else {
                                if ((p.prev = hiTail) == null)
                                    hi = p;
                                else
                                    hiTail.next = p;
                                hiTail = p;
                                ++hc;
                            }
                        }
                        ln = (lc <= UNTREEIFY_THRESHOLD) ? untreeify(lo) :
                            (hc != 0) ? new TreeBin<K,V>(lo) : t;
                        hn = (hc <= UNTREEIFY_THRESHOLD) ? untreeify(hi) :
                            (lc != 0) ? new TreeBin<K,V>(hi) : t;
                        setTabAt(nextTab, i, ln);
                        setTabAt(nextTab, i + n, hn);
                        setTabAt(tab, i, fwd);
                        advance = true;
                    }
                }
            }
        }
    }
}
```






## 一些并发问题：
### 怎么保证一个桶范围和一个线程一一对应？  
有一个全局的volatile变量transferIndex。它记录最新的哈希桶迁移索引。  
每个线程通过cas的方式获取自己的哈希桶范围。如果有多个线程预期的哈希桶范围都一样，  
那么因为cas的原因，只有一个线程可以拥有这段范围并且更新transferIndex的值。其它线程自旋等待，超时才进入下一步  
具体见下面这段解释：


```java
Node<K,V> f; int fh;
        while (advance) { // 此循环的作用是 1.确定当前线程要迁移的桶的范围；2.通过更新i的值确定当前范围内下一个要处理的节点
            int nextIndex, nextBound;
            if (--i >= bound || finishing) // 每次循环都检查结束条件：i自减没有超过下界，finishing标识为true时，跳出while循环
                advance = false;
            else if ((nextIndex = transferIndex) <= 0) { // 迁移总进度<=0，表示所有桶都已迁移完成
                i = -1;
                advance = false;
            }
                /*
                    下面这段代码通过cas的方式确定自己负责的桶范围。
                    假如有多个线程都执行到了下面这行代码，
                    怎么保证只有一个线程可以cas成功？或者说，32-16的桶范围只有一个线程可以拿到？
                    U是一个unsafe对象，可以直接操作内存
                    TRANSFERINDEX通过U这个unsafe对象获取了transferIndex的内存地址，
                    修改TRANSFERINDEX就等于直接修改transferIndex
                    而transferIndex是一个volatile变量
                    每个线程在TRANSFERINDEX = nextIndex时都会请求发出写屏障修改TRANSFERINDEX
                    但是CPU的总线仲裁机制能够保证：
                    只有一个线程可以发出写屏障更新TRANSFERINDEX(transferIndex)
                    并且向CPU总线发出广播，让其它线程的缓存块失效
                    等它们从主内存更新缓存块后，cas的条件已经不成立了。于是陷入自旋
                    自旋超时后，会返回false，执行后面的代码。
                    可能这时已经扩容完了没它事。
                    竞争失败后就相当于走了个过场。
                */
            else if (U.compareAndSwapInt
                     (this, TRANSFERINDEX, nextIndex,
                      nextBound = (nextIndex > stride ?
                                   nextIndex - stride : 0))) { // CAS执行transferIndex=transferIndex-stride，即transferIndex减去已分配出去的桶，得到边界，这里为下界
                bound = nextBound; // 当前线程需要处理的桶下标的下界
                i = nextIndex - 1; // 当前线程需要处理的桶下标
                advance = false;
            }
        }
```

### 只用CAS操作也能做到可见性，为什么transferIndex还要用volatile修饰？
CAS的可见性很局限，对于CAS操作里的变量，只有在执行CAS操作时才能得知它在主内存里的最新值，不通过CAS去访问变量得到的还是线程本地内存里的旧值。  
所以还需要volatile去保证任意时刻的可见性

TRANSFERINDEX在源码的6357行通过unsafe对象获取了transferIndex的内存地址  
![](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-08-27-concurrentHashMap/img_3.png) 




