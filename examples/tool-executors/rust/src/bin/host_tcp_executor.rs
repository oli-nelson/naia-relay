use serde_json::{json, Value};
use std::env;
use std::io::{BufRead, BufReader, Write};
use std::net::TcpStream;
use std::time::{SystemTime, UNIX_EPOCH};

fn new_message_id() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("msg_{nanos}")
}

fn send(stream: &mut TcpStream, message: Value) {
    writeln!(stream, "{message}").unwrap();
    stream.flush().unwrap();
}

fn status_response(message: &Value, status: &str, code: Option<&str>, text: Option<&str>) -> Value {
    json!({
        "protocol": "tep",
        "version": "1.0",
        "message_type": format!("{}_response", message["message_type"].as_str().unwrap_or("unknown")),
        "message_id": new_message_id(),
        "session_id": message["session_id"].as_str().unwrap_or("sess_rust_tcp_executor"),
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
        "session_id": message["session_id"].as_str().unwrap_or("sess_rust_tcp_executor"),
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
    let mut args = env::args().skip(1);
    let host = args.next().unwrap_or_else(|| "127.0.0.1".to_string());
    let port = args
        .next()
        .expect("usage: cargo run --bin host_tcp_executor -- <host> <port>");
    let mut stream = TcpStream::connect(format!("{host}:{port}")).expect("tcp connect failed");
    let reader_stream = stream.try_clone().expect("clone stream failed");
    let mut reader = BufReader::new(reader_stream);
    let mut line = String::new();

    send(
        &mut stream,
        json!({
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_executor",
            "message_id": new_message_id(),
            "session_id": "sess_rust_tcp_executor",
            "payload": {
                "executor_id": "rust-tcp-example",
                "display_name": "Rust tcp example",
                "capabilities": {
                    "tools": true,
                    "resources": false,
                    "prompts": false
                },
                "metadata": {}
            }
        }),
    );
    if reader.read_line(&mut line).unwrap() == 0 {
        return;
    }
    line.clear();

    send(
        &mut stream,
        json!({
            "protocol": "tep",
            "version": "1.0",
            "message_type": "register_tools",
            "message_id": new_message_id(),
            "session_id": "sess_rust_tcp_executor",
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
        }),
    );
    if reader.read_line(&mut line).unwrap() == 0 {
        return;
    }
    line.clear();

    loop {
        if reader.read_line(&mut line).unwrap() == 0 {
            break;
        }
        let Ok(message) = serde_json::from_str::<Value>(&line) else {
            line.clear();
            continue;
        };
        let message_type = message["message_type"].as_str().unwrap_or("");

        match message_type {
            "execute_tool" => {
                let text = format!(
                    "rust tcp executor received: {}",
                    message["payload"]["arguments"]["message"].as_str().unwrap_or("")
                );
                send(&mut stream, execution_result(&message, text));
            }
            "heartbeat" | "shutdown" | "disconnect_notice" => {
                send(&mut stream, status_response(&message, "ok", None, None));
                if message_type == "shutdown" {
                    break;
                }
            }
            other => {
                send(
                    &mut stream,
                    status_response(
                        &message,
                        "error",
                        Some("unsupported"),
                        Some(&format!("unsupported message type: {other}")),
                    ),
                );
            }
        }

        line.clear();
    }
}
