---
layout: post
title: "How Can One Server Handle Multiple Clients?"
date: 2026-11-03
categories: [Systems]
description: "Follow a client request from its machine to the server, and understand why a blocking server gets stuck on one client."
---

Imagine three clients connecting to our server. Each client wants to send data and receive a response.

Our current server handles one client at a time. Let's follow what happens when a client sends data, then see why this becomes a problem.

## What happens when a client sends data?

Suppose Client A sends the bytes `PING` to our server.

The data travels through several steps:

1. Our client program calls `send()` on its socket.
2. The client's operating system takes the bytes, handles the TCP/IP networking work, and sends packets through the network interface.
3. Those packets travel across the network to the server machine.
4. The server's network interface receives them. The server operating system processes the packets and places the received data in the socket's receive buffer.
5. Our server program calls `recv()` to read from that socket. If no data has arrived yet, a blocking `recv()` makes the server wait. When data arrives, the operating system wakes the waiting server, and `recv()` returns the available bytes.

So the application does not read directly from the network cable. The operating system receives network data and makes it available through the socket. Our program reads it using socket operations such as `recv()`.

## Why does our server get stuck?

Our first TCP server follows this flow:

1. Call `accept()` and wait for a client connection.
2. Call `recv()` to read from that client.
3. Process the data and send a response.
4. Keep handling that client until it disconnects.
5. Go back to `accept()` for another client.

Now imagine Client A connects, but does not send any data yet.

Our server calls `recv()` for Client A. Because the socket is blocking and no data has arrived, the server waits there.

Meanwhile, Client B and Client C connect and send data. Their machines send the data through the network, and the server's operating system receives it and places it in their respective socket buffers.

But our server program is still waiting inside the `recv()` for Client A. It has not returned to `accept()` to take Client B or Client C, so it cannot read their data yet.

**The operating system has received their data, but our application is not getting a chance to process it.**

That's the problem with this design: waiting for one client's data stops the server from handling other clients.

Arpit Bhayani demonstrates this one-client-at-a-time behaviour in his synchronous TCP server walkthrough:

- [Building a Simple Synchronous TCP Echo Server](https://edge.arpitbhayani.me/videos/building-simple-tcp-echo-server-redis-internals)

## What do we want instead?

We want the server to handle whichever client has data ready, rather than wait for one particular client.

For example:

- Client A has no data yet, so the server should not remain stuck waiting for A.
- Client B has sent data, so the server reads and handles B's request.
- Client C has also sent data, so the server handles C.
- When A's data arrives, the server handles A too.

To do this, the server needs a way to wait for activity across multiple client sockets and find out which ones are ready to read.

One way to build this is an **event loop with non-blocking sockets**. The operating system can report when sockets are ready, and the server can read from those sockets instead of blocking on just one client.

We'll explore that approach next, following the same path from the socket and operating-system behaviour to the event-loop code.

Arpit's event-loop walkthrough is a useful companion:

- [Event Loops Internals: How Redis Handles Concurrent Connections on a Single Thread](https://arpitbhayani.me/videos/event-loops-internals-redis-concurrent-connections)
