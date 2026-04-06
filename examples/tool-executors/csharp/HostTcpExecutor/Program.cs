using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: dotnet run --project HostTcpExecutor -- <host> <port>");
    return;
}

var host = args[0];
var port = int.Parse(args[1]);

static string NewMessageId() => $"msg_{Guid.NewGuid():N}";

static async Task SendAsync(StreamWriter writer, JsonObject message)
{
    await writer.WriteLineAsync(message.ToJsonString());
    await writer.FlushAsync();
}

static async Task<JsonObject?> ReadMessageAsync(StreamReader reader)
{
    var line = await reader.ReadLineAsync();
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
        ["session_id"] = request["session_id"]?.ToString() ?? "sess_csharp_tcp_executor",
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
        ["session_id"] = request["session_id"]?.ToString() ?? "sess_csharp_tcp_executor",
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

using var client = new TcpClient();
await client.ConnectAsync(host, port);
await using var stream = client.GetStream();
using var reader = new StreamReader(stream, Encoding.UTF8);
using var writer = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true };

await SendAsync(writer, new JsonObject
{
    ["protocol"] = "tep",
    ["version"] = "1.0",
    ["message_type"] = "register_executor",
    ["message_id"] = NewMessageId(),
    ["session_id"] = "sess_csharp_tcp_executor",
    ["payload"] = new JsonObject
    {
        ["executor_id"] = "csharp-tcp-example",
        ["display_name"] = "C# tcp example",
        ["capabilities"] = new JsonObject
        {
            ["tools"] = true,
            ["resources"] = false,
            ["prompts"] = false,
        },
        ["metadata"] = new JsonObject(),
    },
});

if (await ReadMessageAsync(reader) is null) return;

await SendAsync(writer, new JsonObject
{
    ["protocol"] = "tep",
    ["version"] = "1.0",
    ["message_type"] = "register_tools",
    ["message_id"] = NewMessageId(),
    ["session_id"] = "sess_csharp_tcp_executor",
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

if (await ReadMessageAsync(reader) is null) return;

while (true)
{
    var message = await ReadMessageAsync(reader);
    if (message is null) return;

    var messageType = message["message_type"]?.ToString();
    if (messageType == "execute_tool")
    {
        var text = $"csharp tcp executor received: {message["payload"]?["arguments"]?["message"]?.ToString() ?? ""}";
        await SendAsync(writer, ExecutionResult(message, text));
        continue;
    }

    if (messageType is "heartbeat" or "shutdown" or "disconnect_notice")
    {
        await SendAsync(writer, StatusResponse(message));
        if (messageType == "shutdown") return;
        continue;
    }

    await SendAsync(writer, StatusResponse(message, status: "error", code: "unsupported", text: $"unsupported message type: {messageType}"));
}
