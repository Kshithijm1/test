"use client";
import {
    Box, Typography, Button, CircularProgress,
    Dialog, DialogTitle, DialogContent, DialogActions,
    TextField, IconButton
} from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { ChartData, PlotlyChart } from "../../classes/charts";
import Plotly from "plotly.js-dist-min";
import jsPDF from "jspdf";

interface GraphBoxProps {
    charts: ChartData[];
    onChartsChange?: (charts: ChartData[]) => void; // callback to update parent
}

export default function GraphBox({ charts, onChartsChange }: GraphBoxProps) {
    const bottomRef = useRef<HTMLDivElement>(null);
    const chartRefs = useRef<(HTMLDivElement | null)[]>([]);
    const [downloading, setDownloading] = useState(false);

    // Edit modal state
    const [editIdx, setEditIdx] = useState<number | null>(null);
    const [editData, setEditData] = useState("");
    const [editLayout, setEditLayout] = useState("");
    const [editError, setEditError] = useState("");

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [charts]);

    // Open modal and pre-populate with current chart JSON
    const handleEditOpen = (idx: number) => {
        setEditIdx(idx);
        setEditData(JSON.stringify(charts[idx].data, null, 2));
        setEditLayout(JSON.stringify(charts[idx].layout, null, 2));
        setEditError("");
    };

    const handleEditClose = () => {
        setEditIdx(null);
        setEditError("");
    };

    const handleEditSave = () => {
        try {
            const parsedData = JSON.parse(editData);
            const parsedLayout = JSON.parse(editLayout);

            if (!onChartsChange) return;

            const updated = charts.map((chart, i) =>
                i === editIdx
                    ? { ...chart, data: parsedData, layout: parsedLayout }
                    : chart
            );
            onChartsChange(updated);
            handleEditClose();
        } catch (e) {
            setEditError("Invalid JSON — please check your syntax and try again.");
        }
    };

    const handleDownloadAll = async () => {
        if (charts.length === 0) return;
        setDownloading(true);
        try {
            const pdf = new jsPDF({ orientation: "portrait", unit: "px", format: "a4" });
            const pageWidth = pdf.internal.pageSize.getWidth();
            const margin = 30;
            const imgWidth = pageWidth - margin * 2;
            const imgHeight = imgWidth * 0.6;

            for (let i = 0; i < chartRefs.current.length; i++) {
                const el = chartRefs.current[i];
                if (!el) continue;
                const plotlyDiv = el.querySelector(".js-plotly-plot") as HTMLElement;
                if (!plotlyDiv) continue;

                const imgData = await Plotly.toImage(plotlyDiv, {
                    format: "png",
                    width: 800,
                    height: 480,
                });

                if (i > 0) pdf.addPage();
                pdf.setFontSize(10);
                pdf.setTextColor(144, 164, 192);
                pdf.text(`Chart ${i + 1}`, margin, margin - 10);
                pdf.addImage(imgData, "PNG", margin, margin, imgWidth, imgHeight);
            }
            pdf.save("charts.pdf");
        } finally {
            setDownloading(false);
        }
    };

    return (
        <Box
            sx={{
                display: "flex",
                flexDirection: "column",
                height: "100%",
                borderRadius: 3,
                overflow: "hidden",
                border: "1px solid #e3eaf5",
            }}
        >
            {/* Header */}
            <Box
                sx={{
                    px: 2.5,
                    py: 1.5,
                    borderBottom: "1px solid #e3eaf5",
                    bgcolor: "white",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexShrink: 0,
                }}
            >
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: "#1976d2" }} />
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "#1a1a2e", letterSpacing: 0.3 }}>
                        Visualizations
                    </Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    {charts.length > 0 && (
                        <Typography variant="caption" sx={{ color: "#90a4c0", fontWeight: 500 }}>
                            {charts.length} chart{charts.length !== 1 ? "s" : ""}
                        </Typography>
                    )}
                    {charts.length > 0 && (
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={handleDownloadAll}
                            disabled={downloading}
                            startIcon={downloading ? <CircularProgress size={12} thickness={5} /> : <DownloadIcon />}
                            sx={{
                                fontSize: "0.7rem",
                                textTransform: "none",
                                borderColor: "#c5d8f5",
                                color: "#1976d2",
                                px: 1.5,
                                py: 0.4,
                                borderRadius: "6px",
                                "&:hover": { borderColor: "#1976d2", bgcolor: "#f0f7ff" },
                            }}
                        >
                            {downloading ? "Exporting..." : "Download All"}
                        </Button>
                    )}
                </Box>
            </Box>

            {/* Chart list */}
            <Box
                sx={{
                    flex: 1,
                    overflowY: "auto",
                    px: 2,
                    py: 2,
                    display: "flex",
                    flexDirection: "column",
                    gap: 3,
                    bgcolor: "#f8fafd",
                    "&::-webkit-scrollbar": { width: 6 },
                    "&::-webkit-scrollbar-thumb": { bgcolor: "#c5d8f5", borderRadius: 10 },
                }}
            >
                {charts.length === 0 ? (
                    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2, mt: 6, opacity: 0.6 }}>
                        <Box sx={{ position: "relative", width: 80, height: 60 }}>
                            {[0, 1, 2, 3].map((col) =>
                                [0, 1, 2].map((row) => (
                                    <Box
                                        key={`${col}-${row}`}
                                        sx={{
                                            position: "absolute",
                                            left: col * 22,
                                            bottom: row * 22,
                                            width: 16,
                                            height: (row + 1) * 14 + col * 4,
                                            bgcolor: "rgba(25,118,210,0.25)",
                                            borderRadius: "3px 3px 0 0",
                                            opacity: 0.3 + (col + row) * 0.1,
                                        }}
                                    />
                                ))
                            )}
                        </Box>
                        <Typography sx={{ color: "#a0aec0", textAlign: "center", fontSize: 14, fontStyle: "italic" }}>
                            No charts yet. Ask for a graph to see it here.
                        </Typography>
                    </Box>
                ) : (
                    charts.map((chart, idx) => (
                        <Box
                            key={idx}
                            ref={(el: HTMLDivElement | null) => { chartRefs.current[idx] = el; }}
                            sx={{
                                bgcolor: "white",
                                borderRadius: 2,
                                p: 2,
                                border: "1px solid #e3eaf5",
                                boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
                                transition: "border-color 0.2s ease, box-shadow 0.2s ease",
                                "&:hover": { borderColor: "#90c2ff", boxShadow: "0 2px 12px rgba(25,118,210,0.1)" },
                            }}
                        >
                            {/* Label row */}
                            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.5 }}>
                                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                                    <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: "#1976d2" }} />
                                    <Typography sx={{ fontSize: "0.68rem", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: "#90a4c0" }}>
                                        Chart {idx + 1}
                                    </Typography>
                                </Box>
                                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                                    <Box sx={{ fontSize: "0.65rem", color: "#90a4c0", bgcolor: "#f0f4fb", border: "1px solid #e3eaf5", px: 1, py: 0.25, borderRadius: "4px", letterSpacing: "0.04em" }}>
                                        Generated
                                    </Box>
                                    {/* Edit button */}
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        onClick={() => handleEditOpen(idx)}
                                        startIcon={<EditIcon />}
                                        sx={{
                                            fontSize: "0.65rem",
                                            textTransform: "none",
                                            borderColor: "#e3eaf5",
                                            color: "#90a4c0",
                                            px: 1,
                                            py: 0.25,
                                            borderRadius: "4px",
                                            minWidth: 0,
                                            "&:hover": { borderColor: "#1976d2", color: "#1976d2", bgcolor: "#f0f7ff" },
                                        }}
                                    >
                                        Edit
                                    </Button>
                                </Box>
                            </Box>

                            <PlotlyChart data={chart.data} layout={chart.layout} />
                        </Box>
                    ))
                )}
                <div ref={bottomRef} />
            </Box>

            {/* Edit Modal */}
            <Dialog
                open={editIdx !== null}
                onClose={handleEditClose}
                maxWidth="md"
                fullWidth
                PaperProps={{
                    sx: { borderRadius: 3, border: "1px solid #e3eaf5" }
                }}
            >
                <DialogTitle sx={{ pb: 1, fontWeight: 600, color: "#1a1a2e", fontSize: "1rem" }}>
                    Edit Chart {editIdx !== null ? editIdx + 1 : ""}
                </DialogTitle>

                <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
                    {editError && (
                        <Box sx={{ bgcolor: "#fff0f0", border: "1px solid #ffcdd2", borderRadius: 2, px: 2, py: 1 }}>
                            <Typography sx={{ color: "#c62828", fontSize: "0.8rem" }}>{editError}</Typography>
                        </Box>
                    )}

                    <Box>
                        <Typography sx={{ fontSize: "0.75rem", fontWeight: 600, color: "#90a4c0", mb: 0.5, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                            Data
                        </Typography>
                        <TextField
                            multiline
                            fullWidth
                            minRows={8}
                            maxRows={14}
                            value={editData}
                            onChange={(e) => setEditData(e.target.value)}
                            inputProps={{ style: { fontFamily: "monospace", fontSize: "0.8rem" } }}
                            sx={{
                                "& .MuiOutlinedInput-root": {
                                    borderRadius: 2,
                                    bgcolor: "#f8fafd",
                                    "& fieldset": { borderColor: "#e3eaf5" },
                                    "&:hover fieldset": { borderColor: "#90c2ff" },
                                    "&.Mui-focused fieldset": { borderColor: "#1976d2" },
                                }
                            }}
                        />
                    </Box>

                    <Box>
                        <Typography sx={{ fontSize: "0.75rem", fontWeight: 600, color: "#90a4c0", mb: 0.5, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                            Layout
                        </Typography>
                        <TextField
                            multiline
                            fullWidth
                            minRows={5}
                            maxRows={10}
                            value={editLayout}
                            onChange={(e) => setEditLayout(e.target.value)}
                            inputProps={{ style: { fontFamily: "monospace", fontSize: "0.8rem" } }}
                            sx={{
                                "& .MuiOutlinedInput-root": {
                                    borderRadius: 2,
                                    bgcolor: "#f8fafd",
                                    "& fieldset": { borderColor: "#e3eaf5" },
                                    "&:hover fieldset": { borderColor: "#90c2ff" },
                                    "&.Mui-focused fieldset": { borderColor: "#1976d2" },
                                }
                            }}
                        />
                    </Box>
                </DialogContent>

                <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
                    <Button
                        onClick={handleEditClose}
                        sx={{ textTransform: "none", color: "#90a4c0", fontSize: "0.85rem" }}
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleEditSave}
                        variant="contained"
                        sx={{
                            textTransform: "none",
                            borderRadius: "8px",
                            fontSize: "0.85rem",
                            bgcolor: "#1976d2",
                            "&:hover": { bgcolor: "#1565c0" },
                        }}
                    >
                        Apply Changes
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}

function DownloadIcon() {
    return (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 9h-4V3H9v6H5l7 7 7-7zm-8 2V5h2v6h1.17L12 13.17 9.83 11H11zm-6 7h14v2H5v-2z" />
        </svg>
    );
}

function EditIcon() {
    return (
        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm2.92 1.42L15.37 9.22l1.41 1.41L7.33 20.08H5.92v-1.41zM20.71 5.63l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83a1 1 0 0 0 0-1.41z" />
        </svg>
    );
}
