using System.Text.Json;
using System.Text.Json.Nodes;

static string NewMessageId() => $"msg_{Guid.NewGuid():N}";

static void Send(JsonObject message)
{
    Console.Out.WriteLine(message.ToJsonString());
    Console.Out.Flush();
}

static JsonObject? ReadMessage()
{
    var line = Console.ReadLine();
    return line is null ? null : JsonNode.Parse(line)!.AsObject();
}

static JsonObject StatusResponse(JsonObject request, string status = "ok", JsonObject? details = null, string? code = null, string? text = null)
{
    return new JsonObject
    {
        ["protocol"] = "tep",
        ["version"] = "1.0",
        ["message_type"] = $"{request["message_type"]}_response",
        ["message_id"] = NewMessageId(),
        ["session_id"] = request["session_id"]?.ToString() ?? "sess_csharp_stdio_executor",
        ["request_id"] = request["request_id"]?.ToString() ?? request["message_id"]?.ToString(),
        ["execution_id"] = request["execution_id"]?.ToString(),
        ["payload"] = new JsonObject
        {
            ["status"] = status,
            ["code"] = code,
            ["message"] = text,
            ["details"] = details ?? new JsonObject(),
        },
    };
}

static JsonObject ExecutionResult(JsonObject request, string text)
{
    return new JsonObject
    {
        ["protocol"] = "tep",
        ["version"] = "1.0",
        ["message_type"] = "execution_result",
        ["message_id"] = NewMessageId(),
        ["session_id"] = request["session_id"]?.ToString() ?? "sess_csharp_stdio_executor",
        ["request_id"] = request["request_id"]?.ToString() ?? request["message_id"]?.ToString(),
        ["execution_id"] = request["execution_id"]?.ToString(),
        ["payload"] = new JsonObject
        {
            ["tool_name"] = request["payload"]?["tool_name"]?.ToString(),
            ["result"] = new JsonObject
            {
                ["content"] = new JsonArray
                {
                    new JsonObject
                    {
                        ["type"] = "text",
                        ["text"] = text,
                    }
                },
                ["isError"] = false,
            },
            ["is_error"] = false,
            ["metadata"] = new JsonObject(),
        },
    };
}

Send(new JsonObject
{
    ["protocol"] = "tep",
    ["version"] = "1.0",
    ["message_type"] = "register_executor",
    ["message_id"] = NewMessageId(),
    ["session_id"] = "sess_csharp_stdio_executor",
    ["payload"] = new JsonObject
    {
        ["executor_id"] = "csharp-stdio-example",
        ["display_name"] = "C# stdio example",
        ["capabilities"] = new JsonObject
        {
            ["tools"] = true,
            ["resources"] = false,
            ["prompts"] = false,
        },
        ["metadata"] = new JsonObject(),
    },
});

if (ReadMessage() is null) return;

Send(new JsonObject
{
    ["protocol"] = "tep",
    ["version"] = "1.0",
    ["message_type"] = "register_tools",
    ["message_id"] = NewMessageId(),
    ["session_id"] = "sess_csharp_stdio_executor",
    ["payload"] = new JsonObject
    {
        ["tools"] = new JsonArray
        {
            new JsonObject
            {
                ["name"] = "echo",
                ["description"] = "Echoes the input message",
                ["input_schema"] = new JsonObject
                {
                    ["type"] = "object",
                    ["properties"] = new JsonObject
                    {
                        ["message"] = new JsonObject { ["type"] = "string" },
                    },
                    ["required"] = new JsonArray("message"),
                },
                ["metadata"] = new JsonObject(),
            },
        },
    },
});

if (ReadMessage() is null) return;

while (true)
{
    var message = ReadMessage();
    if (message is null) return;

    var messageType = message["message_type"]?.ToString();
    if (messageType == "execute_tool")
    {
        var text = $"csharp stdio executor received: {message["payload"]?["arguments"]?["message"]?.ToString() ?? ""}";
        Send(ExecutionResult(message, text));
        continue;
    }

    if (messageType is "heartbeat" or "shutdown" or "disconnect_notice")
    {
        Send(StatusResponse(message));
        if (messageType == "shutdown") return;
        continue;
    }

    Send(StatusResponse(message, status: "error", code: "unsupported", text: $"unsupported message type: {messageType}"));
}
