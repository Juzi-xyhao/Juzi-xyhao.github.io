---
title: TreeMap & HashMap
tags:
  - JUC
  - Java
  - Synchronized
categories: [Java,HashMap]
author: xyhao
keywords: TreeMap由红黑树实现，HashMap由数组+链表+红黑树实现
description: TreeMap由红黑树实现，HashMap由数组+链表+红黑树实现
top_img: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/articleCover/2024-05-02-Hash.png
cover: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/articleCover/2024-05-02-Hash.png
abbrlink: '81482818'
date: 2024-04-28 00:00:00
---

# **内部实现**：
- HashMap 使用哈希表（基于数组和链表/红黑树的组合）实现，通过计算键的哈希值来快速访问值。
- TreeMap 使用红黑树实现，这使得它能够保持键的自然排序或自定义排序。
# **排序特性**：

- HashMap 不保证任何特定的顺序，键值对的存储和检索顺序可能随时间变化。
- TreeMap 则保持了键的排序，要么按照键的升序（Comparable），要么按照自定义比较器（Comparator）排序，这使得你可以有序地遍历键值对。
# 性能：

- 在平均情况下，HashMap 的插入、删除和查找操作的性能较好，接近 O(1)。
- TreeMap 的插入、删除和查找操作的性能略逊，为 O(log n)，但由于有序性，在某些场景下可能更适合。
# **线程安全性**：

- 它们两者都是非线程安全的。但是hashMap有线程安全的版本，treeMap没有
> **面试可能会问：如何把treeMap修改为线程安全的？**
> 最好的方法是使用替代品，比如ConcurrentSkipListMap。他与treemap一样实现了排序功能，不过是基于跳表实现的。ConcurrentSkipListMap保持了元素的有序性，并允许高并发的插入、删除和访问操作，非常适合那些需要线程安全且按键排序的场景。
> 
> 其次：

```java
    private V put(K key, V value, boolean replaceOld) {
        Entry<K,V> t = root;
        if (t == null) {
            addEntryToEmptyMap(key, value);
            return null;
        }
        int cmp;
        Entry<K,V> parent;
        // split comparator and comparable paths
        Comparator<? super K> cpr = comparator;
        if (cpr != null) {
            do {
                parent = t;
                cmp = cpr.compare(key, t.key);
                if (cmp < 0)
                    t = t.left;
                else if (cmp > 0)
                    t = t.right;
                else {
                    V oldValue = t.value;
                    if (replaceOld || oldValue == null) {
                        t.value = value;
                    }
                    return oldValue;
                }
            } while (t != null);
        } else {
            Objects.requireNonNull(key);
            @SuppressWarnings("unchecked")
            Comparable<? super K> k = (Comparable<? super K>) key;
            //这里通过do-while循环判断有没有树上的节点的key与新节点的key重复
            //如果有就替换value，return
            do {
                parent = t;
                cmp = k.compareTo(t.key);
                if (cmp < 0)
                    t = t.left;
                else if (cmp > 0)
                    t = t.right;
                else {
                    V oldValue = t.value;
                    if (replaceOld || oldValue == null) {
                        t.value = value;
                    }
                    return oldValue;
                }
            } while (t != null);
        }
        addEntry(key, value, parent, cmp < 0);
        return null;
    }

    private void addEntry(K key, V value, Entry<K, V> parent, boolean addToLeft) {
        Entry<K,V> e = new Entry<>(key, value, parent);
        if (addToLeft)
            parent.left = e;
        else
            parent.right = e;
        fixAfterInsertion(e);
        size++;
        modCount++;
    }
```
> 可以给52行new出来的节点上锁，这样就线程安全了



# 为什么HashMap线程不安全？

- 数据丢失
```java
public V put(K key, V value) {
    if (table == EMPTY_TABLE) {
        inflateTable(threshold);
    }
    if (key == null)
        return putForNullKey(value);
    int hash = hash(key);
    int i = indexFor(hash, table.length);
    for (Entry e = table[i]; e != null; e = e.next) {
        Object k;
        if (e.hash == hash && ((k = e.key) == key || key.equals(k))) {
            V oldValue = e.value;
            e.value = value;
            e.recordAccess(this);
            return oldValue;
        }
    }

    modCount++;
    addEntry(hash, key, value, i);
    return null;
}

void addEntry(int hash, K key, V value, int bucketIndex) {
    if ((size >= threshold) && (null != table[bucketIndex])) {
        resize(2 * table.length);
        hash = (null != key) ? hash(key) : 0;
        bucketIndex = indexFor(hash, table.length);
    }

    createEntry(hash, key, value, bucketIndex);
}


void createEntry(int hash, K key, V value, int bucketIndex) {
    Entry e = table[bucketIndex];
    table[bucketIndex] = new Entry<>(hash, key, value, e);
    size++;
```
通过上面Java7中的源码分析一下为什么会出现数据丢失，如果有两条线程同时执行到这条语句 table[i]=null,时两个线程都会区创建Entry,这样存入会出现数据丢失。

- 数据重复

- 扩容时发生死循环（头插法造成，Java8已修复）

![](https://gitee.com/xyhaooo/picrepo/raw/master/articleSource/2024-04-28-TreeMap/v2-114b7455a189ab16390d60491b5c47b2_720w.jpeg)

如果有两个线程同时发现自己都key不存在，而这两个线程的key实际是相同的，在向链表中写入的时候第一线程将e设置为了自己的Entry,而第二个线程执行到了e.next，此时拿到的是最后一个节点，依然会将自己持有是数据插入到链表中，这样就出现了数据 重复。 通过商品put源码可以发现，是先将数据写入到map中，再根据元素到个数再决定是否做resize.在resize过程中还会出现一个更为诡异都问题死循环。 这个原因主要是因为hashMap在resize过程中对链表进行了一次倒序处理。假设两个线程同时进行resize, A->B 第一线程在处理过程中比较慢，第二个线程已经完成了倒序，变成了B-A 那么就出现了循环，B->A->B.这样就出现了就会出现CPU使用率飙升。 在下午突然收到其中一台机器CPU利用率不足告警，将jstack内容分析发现，可能出现了死循环和数据丢失情况，当然对于链表的操作同样存在问题。
 PS:在这个过程中可以发现，之所以出现死循环，主要还是在于对于链表对倒序处理，在Java 8中，已经不在使用倒序列表，死循环问题得到了极大改善。 



> [hashmap的线程不安全体现在哪里？ - 知乎](https://www.zhihu.com/question/28516433/answer/281307231)
