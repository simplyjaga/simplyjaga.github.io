---
layout: post
title: "How Can One Server Handle Multiple Clients?"
date: 2026-11-03
categories: [Systems]
description: "Understanding concurrent client requests, why a simple blocking server gets stuck, and the approaches we can use to serve multiple clients."
---

Imagine a server with three clients connected to it. All three clients want to send a request and receive a response.

How should the server handle them?

At first, this sounds like a simple networking problem. The server accepts a connection, reads a request, processes it, and sends a response. We have already built a server that does exactly this.

But there is a catch: **what happens when multiple clients want the server's attention at the same time?**

Let's understand the problem before looking at the solution.

## What do we mean by concurrent requests?

For this discussion, let's keep the setup deliberately small:

- One server
- Three clients: Client A, Client B, and Client C
- One CPU core executing the server
- No multi-core parallelism and no additional worker threads

Each client sends a request and expects a response. The requests may arrive close together, and the server may need to wait for data from a client before it can do useful work for that client.

The important distinction is between **concurrency** and **parallelism**.

Concurrency means the server can make progress on multiple clients' work during overlapping periods. It does not mean that the CPU executes instructions for all three clients at the exact same instant.

With one CPU core, only one instruction stream is executing at a time. The server can still handle multiple clients concurrently by switching its attention between them: it can work on a client whose data is ready, then move to another while the first client is waiting for more network data.

That is the behaviour we want to understand.

## The problem with handling clients one by one

Our first TCP server follows a straightforward, blocking approach:

1. Wait for a client to connect using `accept()`.
2. Read data from that client's socket.
3. Process the data and write a response.
4. Continue handling that client until it disconnects.
5. Only then return to `accept()` and take the next client.

This works perfectly well when there is only one client.

Now imagine Client A connects and then waits before sending its next request. The server is blocked waiting for data from Client A. Meanwhile, Client B and Client C also connect and send requests.

The server cannot get back to its `accept()` call, because it is still inside the code handling Client A. The operating system can complete the TCP handshakes and queue connections, but our application is not accepting and servicing those clients yet.

So Client B and Client C have to wait—even if their requests are already waiting to be read.

The issue is not that the server has too little processing power. The issue is that **one blocking operation on one client's socket prevents the server from making progress on the others.**

Arpit Bhayani demonstrates this limitation in his walkthrough of a synchronous TCP echo server:

- [Building a Simple Synchronous TCP Echo Server](https://edge.arpitbhayani.me/videos/building-simple-tcp-echo-server-redis-internals)

## What should the server do instead?

We want the server to keep track of all three client connections and make progress on whichever client is ready.

For example:

- Client A sends a request. The server reads and processes it.
- While Client A is waiting for its response or for its next request, Client B becomes ready. The server handles Client B.
- Client C becomes ready next. The server handles Client C.
- Later, if Client A has more data ready, the server comes back to it.

The work is interleaved. The server does not need three CPU cores to make progress on three network connections.

There are several ways to build a server that supports multiple clients:

- **A thread or process per client:** give each connection its own execution context. The operating system schedules those contexts.
- **A thread pool:** accept connections and distribute their work among a bounded set of worker threads.
- **An event loop with non-blocking I/O:** use the operating system to notify the server when a socket is ready, then handle the ready connections from a central loop.

Each approach has different trade-offs. For this exploration, we'll focus on the event-loop approach.

Arpit's event-loop walkthrough is a useful companion to the synchronous-server video:

- [Event Loops Internals: How Redis Handles Concurrent Connections on a Single Thread](https://arpitbhayani.me/videos/event-loops-internals-redis-concurrent-connections)

## What we are going to explore

We'll build our understanding from the same small setup: **three clients, one server, and one CPU core**.

We'll first understand what it means for a socket to be non-blocking, why the server needs to know which sockets are ready, and how the operating system helps it wait for events instead of getting stuck on one client.

Then we'll explore how an event loop uses those notifications to serve multiple clients by interleaving their work.

We'll leave multi-core event-loop designs for a later discussion. For now, the goal is to understand how one execution thread can handle multiple concurrent connections without processing all of them in parallel.
