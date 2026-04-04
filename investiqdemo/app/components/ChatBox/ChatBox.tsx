"use client";
import { Box, Typography } from "@mui/material";
import ReactMarkdown from "react-markdown";
import { ChatMessage } from "../../page";
import { useEffect, useRef } from "react";


interface ChatBoxProps {
    chatMessages: ChatMessage[];
}


export default function ChatBox({ chatMessages }: ChatBoxProps) {
    const bottomRef = useRef<HTMLDivElement>(null);


    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chatMessages]);


    return (
        <Box
            sx={{
                height: "100%",
                overflowY: "auto",
                px: 2,
                py: 2,
                display: "flex",
                flexDirection: "column",
                gap: 1.5,
                "&::-webkit-scrollbar": { width: "6px" },
                "&::-webkit-scrollbar-track": { bgcolor: "transparent" },
                "&::-webkit-scrollbar-thumb": {
                    bgcolor: "#c5d8f5",
                    borderRadius: "10px",
                },
            }}
        >
            {chatMessages.length === 0 && (
                <Box
                    sx={{
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 2,
                        py: 6,
                        opacity: 0.6,
                    }}
                >
                    <Box
                        sx={{
                            width: 40,
                            height: 40,
                            borderRadius: "12px",
                            border: "1px solid #e3eaf5",
                            bgcolor: "white",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            boxShadow: "0 2px 8px rgba(25,118,210,0.08)",
                        }}
                    >
                        <svg
                            width="18"
                            height="18"
                            viewBox="0 0 18 18"
                            fill="none"
                        >
                            <path
                                d="M9 2C5.13 2 2 5.13 2 9s3.13 7 7 7 7-3.13 7-7-3.13-7-7-7zm0 3c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm0 8c-1.66 0-3-1.34-3-3h1c0 1.1.9 2 2 2s2-.9 2-2h1c0 1.66-1.34 3-3 3z"
                                fill="#1976d2"
                            />
                        </svg>
                    </Box>
                    <Typography
                        sx={{
                            fontSize: "0.78rem",
                            color: "#90a4c0",
                            textAlign: "center",
                            lineHeight: 1.6,
                        }}
                    >
                        Ask me anything.
                        <br />I can analyze data and generate charts.
                    </Typography>
                </Box>
            )}


            {chatMessages.map((msg, index) => (
                <Box
                    key={index}
                    sx={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: msg.type === "user" ? "flex-end" : "flex-start",
                        animation: "fadeSlideIn 0.35s ease-out both",
                        "@keyframes fadeSlideIn": {
                            "0%": { opacity: 0, transform: "translateY(10px)" },
                            "100%": { opacity: 1, transform: "translateY(0)" },
                        },
                        // Tighten spacing for consecutive agent messages
                        ...(( msg.type === "agent_step" || msg.type === "agent_output") && {
                            mt: -1,
                        }),
                    }}
                >
                    {/* Role label — only for user and bot messages */}
                    {(msg.type === "user" || msg.type === "bot") && (
                        <Box
                            sx={{
                                fontSize: "0.62rem",
                                fontWeight: 600,
                                letterSpacing: "0.08em",
                                textTransform: "uppercase",
                                color: "#90a4c0",
                                mb: 0.5,
                                px: 0.5,
                            }}
                        >
                            {msg.type === "user" ? "You" : "Assistant"}
                        </Box>
                    )}


                    <Box
                        sx={{
                            maxWidth: "88%",
                            position: "relative",
                            ...(msg.type === "user" && {
                                bgcolor: "#1976d2",
                                color: "white",
                                px: 2,
                                py: 1.25,
                                borderRadius: "12px 12px 2px 12px",
                                fontSize: "0.85rem",
                                lineHeight: 1.6,
                                boxShadow: "0 2px 8px rgba(25,118,210,0.25)",
                            }),
                            ...(msg.type === "bot" && {
                                bgcolor: "white",
                                border: "1px solid #e3eaf5",
                                color: "#1a1a2e",
                                px: 2,
                                py: 1.25,
                                borderRadius: "2px 12px 12px 12px",
                                fontSize: "0.85rem",
                                lineHeight: 1.7,
                                boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
                                "& p": { m: 0, mb: "0.5em" },
                                "& p:last-child": { mb: 0 },
                                "& ul, & ol": { m: 0, pl: 2, mb: "0.5em" },
                                "& pre": {
                                    whiteSpace: "pre-wrap",
                                    m: 0,
                                    bgcolor: "#f8fafd",
                                    p: 1.5,
                                    borderRadius: "6px",
                                    border: "1px solid #e3eaf5",
                                    fontSize: "0.8rem",
                                },
                                "& code": {
                                    fontSize: "0.8rem",
                                    bgcolor: "#f0f4fb",
                                    px: 0.5,
                                    borderRadius: "3px",
                                    color: "#1976d2",
                                },
                                "& strong": { color: "#1a1a2e" },
                            }),
                            ...(msg.type === "thinking" && {
                                bgcolor: "transparent",
                                py: 0.5,
                                px: 0.5,
                                width: "100%",
                            }),
                            ...(msg.type === "agent_step" && {
                                bgcolor: "transparent",
                                py: 0.25,
                                px: 0.5,
                                width: "100%",
                            }),
                            ...(msg.type === "agent_output" && {
                                bgcolor: "transparent",
                                py: 0,
                                px: 0.5,
                                width: "100%",
                            }),
                        }}
                    >
                        {/* ── thinking: pulsing dots bridge before first agent event ── */}
                        {msg.type === "thinking" && (
                            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                                <Box sx={{
                                    width: 14, height: 14, flexShrink: 0, borderRadius: "50%",
                                    border: "2px solid #1976d2",
                                    animation: "spin 1s linear infinite",
                                    borderTopColor: "transparent",
                                    "@keyframes spin": { "0%": { transform: "rotate(0deg)" }, "100%": { transform: "rotate(360deg)" } },
                                }} />
                                <Box sx={{
                                    fontSize: "0.75rem", fontWeight: 600, color: "#1976d2",
                                }}>
                                    Processing...
                                </Box>
                            </Box>
                        )}

                        {/* ── agent_step: "Agent thinking..." / "Agent done" line ── */}
                        {msg.type === "agent_step" && (
                            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                                {msg.agentStatus === "completed" ? (
                                    <Box sx={{ width: 14, height: 14, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                                            <circle cx="7" cy="7" r="7" fill="#22c55e" />
                                            <path d="M4 7l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                        </svg>
                                    </Box>
                                ) : (
                                    <Box sx={{
                                        width: 14, height: 14, flexShrink: 0, borderRadius: "50%",
                                        border: "2px solid #1976d2",
                                        animation: "spin 1s linear infinite",
                                        borderTopColor: "transparent",
                                        "@keyframes spin": { "0%": { transform: "rotate(0deg)" }, "100%": { transform: "rotate(360deg)" } },
                                    }} />
                                )}
                                <Box sx={{
                                    fontSize: "0.75rem", fontWeight: 600,
                                    color: msg.agentStatus === "completed" ? "#1a1a2e" : "#1976d2",
                                }}>
                                    {msg.agentName}{msg.agentStatus === "started" ? " thinking..." : " done"}
                                </Box>
                            </Box>
                        )}

                        {/* ── agent_output: detail blocks (plan, SQL, table, config) ── */}
                        {msg.type === "agent_output" && (() => {
                            const d = msg.detail;
                            return (
                                <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75, width: "100%" }}>
                                    {/* Plan summary text */}
                                    {!d && msg.text && (
                                        <Box sx={{
                                            bgcolor: "#f8fafd", border: "1px solid #e3eaf5",
                                            borderRadius: "6px", px: 1.5, py: 1,
                                            fontSize: "0.68rem", color: "#4a5568",
                                            lineHeight: 1.5, whiteSpace: "pre-wrap",
                                            maxHeight: 160, overflowY: "auto",
                                            "&::-webkit-scrollbar": { width: "4px" },
                                            "&::-webkit-scrollbar-thumb": { bgcolor: "#c5d8f5", borderRadius: "4px" },
                                        }}>
                                            {msg.text}
                                        </Box>
                                    )}

                                    {/* SQL Query box */}
                                    {d?.sql && (
                                        <Box sx={{
                                            bgcolor: "#1a1a2e", color: "#a5d6ff", p: 1.25,
                                            borderRadius: "6px", fontSize: "0.65rem",
                                            fontFamily: "'Fira Code', 'Consolas', monospace",
                                            lineHeight: 1.5, overflowX: "auto",
                                            whiteSpace: "pre-wrap", wordBreak: "break-word",
                                            maxHeight: 160, overflowY: "auto",
                                            "&::-webkit-scrollbar": { width: "4px", height: "4px" },
                                            "&::-webkit-scrollbar-thumb": { bgcolor: "#444", borderRadius: "4px" },
                                        }}>
                                            <Box sx={{ fontSize: "0.58rem", color: "#6b7280", mb: 0.5, fontFamily: "inherit", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                                                SQL Query
                                            </Box>
                                            {d.sql}
                                        </Box>
                                    )}

                                    {/* Data preview table */}
                                    {d?.preview && d?.columns && (
                                        <Box sx={{
                                            border: "1px solid #e3eaf5", borderRadius: "6px",
                                            overflow: "hidden", fontSize: "0.62rem",
                                        }}>
                                            <Box sx={{
                                                fontSize: "0.58rem", color: "#6b7280", px: 1, py: 0.5,
                                                bgcolor: "#f8fafd", borderBottom: "1px solid #e3eaf5",
                                                textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600,
                                            }}>
                                                Data Preview ({d.total_rows} rows total — showing first {d.preview.length})
                                            </Box>
                                            <Box sx={{ overflowX: "auto" }}>
                                                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                                                    <thead>
                                                        <tr>
                                                            {d.columns.map((col: string) => (
                                                                <th key={col} style={{
                                                                    padding: "4px 8px", textAlign: "left",
                                                                    borderBottom: "1px solid #e3eaf5",
                                                                    background: "#f8fafd", fontWeight: 600,
                                                                    fontSize: "0.6rem", color: "#1a1a2e",
                                                                    whiteSpace: "nowrap",
                                                                }}>{col}</th>
                                                            ))}
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {d.preview.map((row: Record<string, any>, ri: number) => (
                                                            <tr key={ri} style={{ backgroundColor: ri % 2 === 0 ? "white" : "#f8fafd" }}>
                                                                {d.columns!.map((col: string) => (
                                                                    <td key={col} style={{
                                                                        padding: "3px 8px", fontSize: "0.6rem",
                                                                        color: "#4a5568", whiteSpace: "nowrap",
                                                                        borderBottom: "1px solid #f0f4fb",
                                                                    }}>
                                                                        {row[col] != null ? String(row[col]) : "—"}
                                                                    </td>
                                                                ))}
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </Box>
                                        </Box>
                                    )}

                                    {/* Chart config JSON */}
                                    {(d?.config || d?.config_raw) && (
                                        <Box sx={{
                                            bgcolor: "#1a1a2e", color: "#c4b5fd", p: 1.25,
                                            borderRadius: "6px", fontSize: "0.65rem",
                                            fontFamily: "'Fira Code', 'Consolas', monospace",
                                            lineHeight: 1.5, overflowX: "auto",
                                            whiteSpace: "pre-wrap", wordBreak: "break-word",
                                            maxHeight: 160, overflowY: "auto",
                                            "&::-webkit-scrollbar": { width: "4px", height: "4px" },
                                            "&::-webkit-scrollbar-thumb": { bgcolor: "#444", borderRadius: "4px" },
                                        }}>
                                            <Box sx={{ fontSize: "0.58rem", color: "#6b7280", mb: 0.5, fontFamily: "inherit", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                                                Chart Config
                                            </Box>
                                            {d.config
                                                ? JSON.stringify(d.config, null, 2)
                                                : d.config_raw}
                                        </Box>
                                    )}
                                </Box>
                            );
                        })()}

                        {/* ── bot: markdown response ── */}
                        {msg.type === "bot" && (
                            <ReactMarkdown>{msg.text || "..."}</ReactMarkdown>
                        )}

                        {/* ── user: plain text ── */}
                        {msg.type === "user" && (
                            <Box component="span" sx={{ whiteSpace: "pre-wrap" }}>
                                {msg.text}
                            </Box>
                        )}
                    </Box>
                </Box>
            ))}


            <div ref={bottomRef} />
        </Box>
    );
}
