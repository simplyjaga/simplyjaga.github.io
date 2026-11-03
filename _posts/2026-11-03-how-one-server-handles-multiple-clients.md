---
layout: post
title: "How Can One Server Handle Multiple Clients?"
date: 2026-11-03
categories: [Systems]
description: "Follow a client request through the operating system and understand why a blocking server gets stuck on one client."
toc:
  - title: "How Can One Server Handle Multiple Clients?"
    url: "#article-start"
    children:
      - title: "What happens when a client sends data?"
        url: "#what-happens-when-a-client-sends-data"
      - title: "Why does a blocking server get stuck?"
        url: "#why-does-a-blocking-server-get-stuck"
      - title: "What do we need instead?"
        url: "#what-do-we-need-instead"
      - title: "The system calls and the programming language"
        url: "#the-system-calls-and-the-programming-language"
---

An event loop allows a server to handle many client connections without waiting for each client one at a time. To understand how it works, we first need to see what happens when data travels from a client to a server.

This post explores that flow and then builds towards the event-loop model.

## What happens when a client sends data? {#what-happens-when-a-client-sends-data}

Suppose Client A sends the bytes `PING` to a server.

The data travels through several steps:

1. The client program asks the operating system to send data through its socket. In Python, this is done using methods such as `send()` or `sendall()`.
2. The client's operating system handles the TCP/IP networking work and sends packets through the machine's network interface.
3. The packets travel across the network to the server machine.
4. The server's network interface receives the packets. The server operating system processes them and places the received data in the socket's receive buffer.
5. The server program asks the operating system to read from that socket. In Python, it can call `recv()`. If the socket is blocking and no data is available, the call waits. When data arrives, the operating system makes the waiting operation ready to continue, and `recv()` returns the available bytes.

The application does not read directly from the network interface. The operating system receives the network data and makes it available through the socket. The application accesses it through the socket API.

## Why does a blocking server get stuck? {#why-does-a-blocking-server-get-stuck}

Consider a simple server that handles one client at a time:

1. Call `accept()` and wait for a client connection.
2. Call `recv()` to read data from that client.
3. Process the data and send a response.
4. Continue handling that client until it disconnects.
5. Return to `accept()` to take another client.

Now imagine Client A connects but does not send any data yet.

The server calls `recv()` for Client A. Because the socket is blocking and no data has arrived, the server waits there.

Meanwhile, Client B and Client C connect and send data. The server operating system receives their packets and places the data in their respective socket receive buffers.

But the server program is still waiting inside the `recv()` call for Client A. It has not returned to `accept()` to accept the other connections, so it cannot read their data yet.

**The operating system has received data for B and C, but the application is still waiting for A.**

That's the limitation of this design: waiting for one client's data prevents the server from handling other clients.

## What do we need instead? {#what-do-we-need-instead}

We want the server to find out which client sockets are ready for I/O, rather than block while waiting for one particular client.

For example:

- Client A has no data yet, so the server should not wait on A.
- Client B has sent data, so the server reads and handles B's request.
- Client C has also sent data, so the server handles C.
- When A's data arrives, the server can handle A too.

An **event loop** provides a way to organise this. It waits for activity on multiple sockets and handles the sockets that are ready. Non-blocking I/O is an important part of this approach.

## The system calls and the programming language {#the-system-calls-and-the-programming-language}

The operating system provides interfaces for operations such as creating sockets, accepting connections, sending and receiving data, and waiting for socket events.

Different operating systems expose these capabilities through different system calls and APIs. Programming languages provide their own interfaces around them. For example, Python's `socket` module gives us methods such as `socket()`, `accept()`, `send()`, and `recv()`; these let us work with sockets without writing the low-level operating-system interface ourselves.

For the examples in this post, we'll use **Python** because its code is straightforward to read. The concepts we discuss—sockets, blocking and non-blocking I/O, readiness notifications, and event loops—are operating-system concepts, not features unique to Python. The same ideas can be explored in other languages using their respective APIs.

We'll build the explanation from the data flow and socket operations, then look at how the operating system can notify a server about sockets that are ready and how the event loop uses that information.
