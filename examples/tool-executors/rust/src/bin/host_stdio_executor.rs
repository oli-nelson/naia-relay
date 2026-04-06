use serde_json::{json, Value};
use std::io::{self, BufRead, Write};
use std::time::{SystemTime, UNIX_EPOCH};

fn new_message_id() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("msg_{nanos}")
}

fn send(message: Value) {
    let mut stdout = io::stdout().lock();
    writeln!(stdout, "{message}").unwrap();
    stdout.flush().unwrap();
}

fn status_response(message: &Value, status: &str, code: Option<&str>, text: Option<&str>) -> Value {
    json!({
        "protocol": "tep",
        "version": "1.0",
        "message_type": format!("{}_response", message["message_type"].as_str().unwrap_or("unknown")),
        "message_id": new_message_id(),
        "session_id": message["session_id"].as_str().unwrap_or("sess_rust_stdio_executor"),
        "request_id": message["request_id"].as_str().or(message["message_id"].as_str()),
        "execution_id": message["execution_id"].as_str(),
        "payload": {
            "status": status,
            "code": code,
            "message": text,
            "details": {}
        }
    })
}

fn execution_result(message: &Value, text: String) -> Value {
    json!({
        "protocol": "tep",
        "version": "1.0",
        "message_type": "execution_result",
        "message_id": new_message_id(),
        "session_id": message["session_id"].as_str().unwrap_or("sess_rust_stdio_executor"),
        "request_id": message["request_id"].as_str().or(message["message_id"].as_str()),
        "execution_id": message["execution_id"].as_str(),
        "payload": {
            "tool_name": message["payload"]["tool_name"].as_str().unwrap_or("echo"),
            "result": {
                "content": [{
                    "type": "text",
                    "text": text
                }],
                "isError": false
            },
            "is_error": false,
            "metadata": {}
        }
    })
}

fn main() {
    send(json!({
        "protocol": "tep",
        "version": "1.0",
        "message_type": "register_executor",
        "message_id": new_message_id(),
        "session_id": "sess_rust_stdio_executor",
        "payload": {
            "executor_id": "rust-stdio-example",
            "display_name": "Rust stdio example",
            "capabilities": {
                "tools": true,
                "resources": false,
                "prompts": false
            },
            "metadata": {}
        }
    }));

    let stdin = io::stdin();
    let mut lines = stdin.lock().lines();
    if lines.next().is_none() {
        return;
    }

    send(json!({
        "protocol": "tep",
        "version": "1.0",
        "message_type": "register_tools",
        "message_id": new_message_id(),
        "session_id": "sess_rust_stdio_executor",
        "payload": {
            "tools": [{
                "name": "echo",
                "description": "Echoes the input message",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": { "type": "string" }
                    },
                    "required": ["message"]
                },
                "metadata": {}
            }]
        }
    }));

    if lines.next().is_none() {
        return;
    }

    for line in lines {
        let Ok(line) = line else { break };
        let Ok(message) = serde_json::from_str::<Value>(&line) else { continue };
        let message_type = message["message_type"].as_str().unwrap_or("");

        match message_type {
            "execute_tool" => {
                let text = format!(
                    "rust stdio executor received: {}",
                    message["payload"]["arguments"]["message"].as_str().unwrap_or("")
                );
                send(execution_result(&message, text));
            }
            "heartbeat" | "shutdown" | "disconnect_notice" => {
                send(status_response(&message, "ok", None, None));
                if message_type == "shutdown" {
                    break;
                }
            }
            other => {
                send(status_response(
                    &message,
                    "error",
                    Some("unsupported"),
                    Some(&format!("unsupported message type: {other}")),
                ));
            }
        }
    }
}
