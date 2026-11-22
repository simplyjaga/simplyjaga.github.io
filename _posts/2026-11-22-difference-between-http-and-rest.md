---
layout: post
title: "The Difference Between HTTP and REST"
date: 2026-11-22
categories: [Systems]
description: "Why REST is a specification rather than a protocol, why it fits HTTP so well, and what the 'S' in HTTPS looks like for a non-HTTP protocol like Redis's RESP."
toc:
  - title: "Is HTTPS coupled to REST?"
    url: "#is-https-coupled-to-rest"
    children:
      - title: "What does HTTPS actually do?"
        url: "#what-does-https-actually-do"
      - title: "What does REST actually define?"
        url: "#what-does-rest-actually-define"
  - title: "How were web APIs designed before REST?"
    url: "#how-were-web-apis-designed-before-rest"
    children:
      - title: "What did an RPC-style call look like?"
        url: "#what-did-an-rpc-style-call-look-like"
  - title: "Why does REST fit HTTP so well?"
    url: "#why-does-rest-fit-http-so-well"
    children:
      - title: "How do the URL and the verb split the work?"
        url: "#how-do-the-url-and-the-verb-split-the-work"
      - title: "How does one URL serve many operations?"
        url: "#how-does-one-url-serve-many-operations"
  - title: "Does REST have to use JSON?"
    url: "#does-rest-have-to-use-json"
    children:
      - title: "What decides the format of a request body?"
        url: "#what-decides-the-format-of-a-request-body"
      - title: "What does 'representational state transfer' actually mean?"
        url: "#what-does-representational-state-transfer-actually-mean"
  - title: "Can HTTPS carry something other than REST?"
    url: "#can-https-carry-something-other-than-rest"
    children:
      - title: "What else runs over HTTPS?"
        url: "#what-else-runs-over-https"
      - title: "What is the HTTPS equivalent for Redis's RESP?"
        url: "#what-is-the-https-equivalent-for-rediss-resp"
      - title: "What does the connection URL tell the client?"
        url: "#what-does-the-connection-url-tell-the-client"
---

References:

- [Roy T. Fielding's PhD dissertation, *Architectural Styles and the Design of Network-based Software Architectures* (2000)](https://ics.uci.edu/~fielding/pubs/dissertation/top.htm)—[Chapter 5](https://ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm) introduces REST.
- [Arpit Bhayani's lecture "Everything you need to know about REST"](https://www.youtube.com/watch?v=uFGJVQvR59A&list=PLsdq-3Z1EPT36NJXTutvKcreetuHCr9a-&index=2).

## Is HTTPS coupled to REST? {#is-https-coupled-to-rest}

No. HTTPS and REST live at different layers of the network stack, which means they can be mixed and matched independently.

### What does HTTPS actually do? {#what-does-https-actually-do}

HTTPS is HTTP encrypted with TLS. Its only job is to move bytes securely from point A to point B. It does not care what the data looks like or how the API is structured.

### What does REST actually define? {#what-does-rest-actually-define}

REST—Representational State Transfer—is a *specification* for how a client asks a server for things and how the server responds. It does not enforce a protocol, a storage engine, or a payload format. Its one big idea: **everything is a resource**—a student, a book, an order—and client and server exchange *representations* of those resources.

REST usually runs over HTTPS in production because REST is most often implemented on HTTP, not because the two are coupled. In principle, REST could sit on another transport entirely—HTTP just happens to fit it beautifully, for reasons the next sections unpack.

## How were web APIs designed before REST? {#how-were-web-apis-designed-before-rest}

Before REST, most web APIs were **remote procedure calls tunneled through HTTP**—the server exposed functions to call, and HTTP was just the delivery mechanism carrying them.

### What did an RPC-style call look like? {#what-did-an-rpc-style-call-look-like}

The action lived in the URL or the body, not in the HTTP method:

~~~http
POST /rpc HTTP/1.1
Content-Type: text/xml

<getUser><id>42</id></getUser>
~~~

\`POST\` was used for everything, even pure reads. The most formal version of this style was **SOAP**: an XML-based messaging protocol that, like REST, usually traveled over HTTP—but unlike REST, it ignored HTTP's methods and described the operation inside the XML envelope. SOAP services often returned \`200 OK\` with a \`<Fault>\` element in the body, so the status code only meant "the envelope arrived," not the outcome. URLs named procedures (\`/getUser\`, \`/updateStudent\`), not resources.

## Why does REST fit HTTP so well? {#why-does-rest-fit-http-so-well}

REST never needed its own protocol—it is a specification, and HTTP already provided all the machinery it required. So well, in fact, that today "writing an HTTP API" and "writing a REST API" feel synonymous—even though they are not the same thing.

### How do the URL and the verb split the work? {#how-do-the-url-and-the-verb-split-the-work}

In a RESTful design, the URL identifies the resource and the HTTP method names the action:

~~~http
DELETE /users/1 HTTP/1.1
~~~

Read it literally: *for the resource "user identified by 1"—delete it.* REST's contribution was to say: use HTTP's verbs the way they were meant to be used. \`GET\` reads \`/users/1\`, \`DELETE\` removes \`/users/1\`, and a missing resource returns \`404\`.

### How does one URL serve many operations? {#how-does-one-url-serve-many-operations}

HTTP methods let you *multiplex* on a single resource URL. \`/students/1\` can accept \`GET\` (read), \`PUT\` or \`PATCH\` (update), and \`DELETE\` (remove)—the URL stays fixed while the method changes the meaning.

This is also a litmus test for whether an endpoint is actually REST: a \`POST /getStudent\` endpoint that takes the student ID in the request body is a perfectly working HTTP endpoint, but it is not REST—the URL names an action instead of identifying a resource.

## Does REST have to use JSON? {#does-rest-have-to-use-json}

No. REST is format-agnostic. JSON is simply the most popular choice today because it is easy to read and work with—being human-friendly matters more to most APIs than being compact.

### What decides the format of a request body? {#what-decides-the-format-of-a-request-body}

The \`Content-Type\` header. A REST API can send and receive any format the client and server agree on—XML, HTML or plain text, compact binary formats like Protocol Buffers or MessagePack, even YAML or CSV.

### What does "representational state transfer" actually mean? {#what-does-representational-state-transfer-actually-mean}

The name encodes the core idea. A resource has an **internal representation**—how it is stored, say rows and columns in a relational database—and an **external representation**—how it is served to the client, say a JSON object. REST only specifies the second part: how client and server communicate. Store data however you want; serve it in whatever representation the client asks for.

A client can request the same resource as JSON, XML, or CSV, and the \`Accept\` and \`Content-Type\` headers are how that negotiation happens—which is exactly why REST slid into HTTP so naturally.

## Can HTTPS carry something other than REST? {#can-https-carry-something-other-than-rest}

Yes, in two different ways: HTTPS can carry other API styles, and its underlying encryption layer—TLS—can protect protocols that do not use HTTP at all.

### What else runs over HTTPS? {#what-else-runs-over-https}

GraphQL, SOAP, and gRPC all run on top of HTTP, so they all use HTTPS directly. They are alternative API styles, not replacements for the transport—GraphQL lets the client query exactly the fields it needs, and gRPC is a direct alternative to REST that trades readable JSON for binary Protobuf over HTTP/2. Each is worth its own exploration.

### What is the HTTPS equivalent for Redis's RESP? {#what-is-the-https-equivalent-for-rediss-resp}

Here is the bigger idea, shown through one comparison: "HTTPS" is not a single thing—it is HTTP wrapped inside TLS, and TLS is an independent encryption layer that can wrap **any** TCP connection. Redis's wire protocol shows what that looks like when HTTP is not involved at all.

Redis speaks RESP (Redis Serialization Protocol), which runs directly over raw TCP rather than HTTP. It is not REST, and it is not HTTP—RESP does not know what \`GET\` or \`POST\` mean in the HTTP sense; it has its own tiny syntax:

~~~text
*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n
~~~

HTTP and RESP are siblings on the same layer. Neither is a type of TCP—both **use** TCP as their delivery pipe. TCP guarantees that bytes arrive in order without loss, regardless of which language is spoken inside the pipe.

So a secured Redis connection is the "HTTPS equivalent" for RESP:

~~~text
HTTPS            =  HTTP  + TLS + TCP
Secure Redis     =  RESP  + TLS + TCP
~~~

When TLS is enabled on a Redis server, the client opens a TCP connection and performs a TLS handshake first—verifying certificates and setting up encryption. Once the encrypted tunnel exists, client and server speak plain RESP inside it. No HTTP is involved anywhere. You would not normally run RESP *inside* HTTPS—the HTTP headers would mean nothing to Redis—unless you deliberately put an HTTP proxy in front of it.

### What does the connection URL tell the client? {#what-does-the-connection-url-tell-the-client}

Just as \`http://\` becomes \`https://\` when TLS is added, Redis connection strings change from \`redis://\` to \`rediss://\`:

- \`redis://user:pass@host:6379\` — plain TCP, RESP sent unencrypted. Fine for localhost or an isolated private network.
- \`rediss://user:pass@host:6379\` — TCP plus a TLS handshake, RESP sent inside the encrypted tunnel. The right choice for production and cloud-hosted Redis.

These URLs are passed to a Redis client library in backend code (such as ioredis, redis-py, or go-redis), not typed into a browser.

The takeaway: each layer makes one decision, and none of them forces the others. TLS can encrypt any TCP protocol. HTTP can carry any body format. And REST is just one specification among several—nothing forces it onto HTTP, JSON, or any particular storage engine.
