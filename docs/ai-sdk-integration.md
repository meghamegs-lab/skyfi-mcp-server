# Vercel AI SDK Integration Guide

This guide shows how to integrate the SkyFi MCP server with the Vercel AI SDK (Node.js) for building satellite imagery applications in TypeScript/JavaScript.

## Prerequisites

Install required packages:

```bash
npm install ai @anthropic-ai/sdk dotenv
# or for OpenAI:
npm install ai openai dotenv
```

Create `.env.local`:

```env
SKYFI_API_KEY=your-skyfi-api-key
ANTHROPIC_API_KEY=sk-ant-...
# or for OpenAI:
# OPENAI_API_KEY=sk-...
```

## Quick Start

### Step 1: Configure MCP Tools

**lib/skyfi-tools.ts**

```typescript
import { Tool } from "ai";

export const skyfiMcpConfig = {
  type: "mcp",
  name: "skyfi",
  url: "https://skyfi-mcp.fly.dev/mcp",
  headers: {
    Authorization: `Bearer ${process.env.SKYFI_API_KEY}`,
  },
};

// Tool categories for reference
export const SKYFI_TOOLS = {
  search: [
    "geocode_location",
    "search_archive",
    "search_archive_next_page",
    "get_archive_details",
  ],
  pricing: [
    "get_pricing_options",
    "check_feasibility",
    "predict_satellite_passes",
  ],
  orders: [
    "create_archive_order",
    "create_tasking_order",
    "list_orders",
    "get_order_status",
    "get_download_url",
  ],
  monitoring: [
    "create_aoi_notification",
    "list_notifications",
    "check_new_images",
  ],
  account: ["get_account_info"],
};
```

### Step 2: Create API Route Handler

**app/api/skyfi/route.ts** (Next.js)

```typescript
import { Anthropic } from "@anthropic-ai/sdk";
import { Message } from "@anthropic-ai/sdk/resources/messages";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const skyfiMcpConfig = {
  type: "mcp" as const,
  name: "skyfi",
  url: "https://skyfi-mcp.fly.dev/mcp",
  headers: {
    Authorization: `Bearer ${process.env.SKYFI_API_KEY}`,
  },
};

export async function POST(request: Request) {
  try {
    const { messages, userMessage } = await request.json();

    // Initialize conversation with user message
    const conversationMessages = [
      ...messages,
      {
        role: "user" as const,
        content: userMessage,
      },
    ];

    // Call Claude with MCP tools
    const response = await client.messages.create({
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 2048,
      system: `You are a helpful satellite imagery assistant powered by SkyFi.

You can:
- Search for satellite imagery by location
- Check pricing and feasibility of orders
- Place orders (always get user confirmation first)
- Monitor areas for new imagery

Always present pricing to the user and get explicit approval before placing orders.`,
      messages: conversationMessages,
      tools: [skyfiMcpConfig] as any,
    });

    return Response.json(response);
  } catch (error) {
    console.error("Error:", error);
    return Response.json(
      { error: "Failed to process request" },
      { status: 500 }
    );
  }
}
```

### Step 3: Client Component

**components/SkyFiChat.tsx**

```typescript
"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function SkyFiChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!input.trim()) return;

    // Add user message
    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // Call API
      const response = await fetch("/api/skyfi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: messages,
          userMessage: input,
        }),
      });

      const data = await response.json();

      // Extract assistant response
      const assistantContent = data.content
        .filter((block: any) => block.type === "text")
        .map((block: any) => block.text)
        .join("\n");

      if (assistantContent) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: assistantContent },
        ]);
      }
    } catch (error) {
      console.error("Error:", error);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, there was an error processing your request.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                msg.role === "user"
                  ? "bg-blue-500 text-white"
                  : "bg-gray-300 text-black"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 bg-white border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about satellite imagery..."
            disabled={isLoading}
            className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {isLoading ? "..." : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
```

## Configuration: TypeScript

**types/skyfi.ts**

```typescript
/**
 * SkyFi MCP Configuration Types
 */

export interface MCPConfig {
  type: "mcp";
  name: string;
  url: string;
  headers: Record<string, string>;
}

export interface SkyFiImage {
  archive_id: string;
  provider: string;
  product_type: string;
  resolution: string;
  capture_date: string;
  cloud_coverage_percent: number;
  gsd_cm: number;
  price_per_sq_km_usd: number;
  price_full_scene_usd: number;
}

export interface PricingOptions {
  pricing: Record<string, any>;
  confirmation_token: string;
  token_valid_for_seconds: number;
}

export interface OrderRequest {
  aoi: string;
  archive_id?: string;
  window_start?: string;
  window_end?: string;
  product_type?: string;
  resolution?: string;
  confirmation_token: string;
}
```

## Advanced: Streaming Responses

**lib/skyfi-stream.ts**

```typescript
import { Anthropic } from "@anthropic-ai/sdk";

const client = new Anthropic();

export async function* streamSkyFiResponse(userMessage: string) {
  const stream = await client.messages.stream({
    model: "claude-3-5-sonnet-20241022",
    max_tokens: 1024,
    messages: [
      {
        role: "user",
        content: userMessage,
      },
    ],
    system: `You are a satellite imagery assistant. Provide concise, helpful responses about satellite imagery.`,
    tools: [
      {
        type: "mcp" as const,
        name: "skyfi",
        url: "https://skyfi-mcp.fly.dev/mcp",
        headers: {
          Authorization: `Bearer ${process.env.SKYFI_API_KEY}`,
        },
      },
    ] as any,
  });

  for await (const chunk of stream) {
    if (
      chunk.type === "content_block_delta" &&
      chunk.delta.type === "text_delta"
    ) {
      yield chunk.delta.text;
    }
  }
}
```

## Use with Vercel AI SDK's `useChat` Hook

**components/StreamingChat.tsx**

```typescript
"use client";

import { useChat } from "ai/react";

export default function StreamingChat() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } =
    useChat({
      api: "/api/skyfi-chat",
      initialMessages: [
        {
          id: "1",
          role: "assistant",
          content:
            "I can help you find and analyze satellite imagery. What location interests you?",
        },
      ],
    });

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="space-y-4 mb-4 h-96 overflow-y-auto">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`p-2 rounded ${
              msg.role === "user" ? "bg-blue-100" : "bg-gray-100"
            }`}
          >
            {msg.content}
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={handleInputChange}
          placeholder="Ask about satellite imagery..."
          className="flex-1 px-3 py-2 border rounded"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading}
          className="px-4 py-2 bg-blue-500 text-white rounded"
        >
          Send
        </button>
      </form>
    </div>
  );
}
```

## Self-Hosted Configuration

For self-hosted SkyFi MCP server:

```typescript
const skyfiMcpConfig = {
  type: "mcp" as const,
  name: "skyfi",
  url: "https://your-domain.com/mcp",
  headers: {
    Authorization: `Bearer ${process.env.SKYFI_API_KEY}`,
  },
};
```

## Error Handling

```typescript
try {
  const response = await client.messages.create({
    model: "claude-3-5-sonnet-20241022",
    messages: conversationMessages,
    tools: [skyfiMcpConfig] as any,
  });
} catch (error) {
  if (error instanceof Anthropic.APIError) {
    if (error.status === 401) {
      console.error("Authentication failed. Check SKYFI_API_KEY.");
    } else {
      console.error("API error:", error.message);
    }
  }
}
```

## What's Next

- **LangChain Integration**: See [langchain-integration.md](langchain-integration.md) for Python agents
- **Google ADK**: See [adk-integration.md](adk-integration.md) for Google's Agent Development Kit
- **Claude Integration**: See [anthropic-api-integration.md](anthropic-api-integration.md) for Anthropic API
- **OpenAI Integration**: See [openai-integration.md](openai-integration.md) for OpenAI API
