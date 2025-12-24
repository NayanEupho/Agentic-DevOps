// Dynamic API Base URL logic
const getApiBase = () => {
    if (typeof window !== 'undefined') {
        const host = window.location.hostname;
        return `http://${host}:8000/api`;
    }
    return "http://localhost:8000/api";
};

// We exporting a function or using a getter?
// Since this file exports functions, we can just call getApiBase() inside them.
// Or we can keep API_BASE as a variable but it might be eval'd too early?
// Let's change usage sites or make API_BASE a getter.
// EASIEST: Just update all functions to use getBase() or similar.
// But to minimize diff, let's redefine how functions use it.

// Helper to get base URL
const getBase = () => {
    if (typeof window !== 'undefined') {
        const url = `http://${window.location.hostname}:8088/api`;
        console.log("[API] Computed Base URL:", url);
        return url;
    }
    return "http://localhost:8088/api";
};


export interface Session {
    id: string;
    title: string;
    last_activity: string;
    message_count: number;
}

export interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    timestamp?: string;
    thoughts?: ThoughtItem[];
}

export interface ThoughtItem {
    type: "status" | "thought" | "tool_call" | "tool_result" | "error";
    content: string;
}

export async function getSessions(): Promise<Session[]> {
    try {
        const res = await fetch(`${getBase()}/sessions`);
        if (!res.ok) return [];
        return await res.json();
    } catch (e) {
        console.error("Session fetch error", e);
        return [];
    }
}

export async function createSession(title: string): Promise<Session | null> {
    try {
        const res = await fetch(`${getBase()}/sessions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
        });
        if (!res.ok) return null;
        return await res.json();
    } catch (e) {
        return null;
    }
}

export async function getSessionHistory(id: string): Promise<any> {
    try {
        const res = await fetch(`${getBase()}/sessions/${id}`);
        if (!res.ok) return null;
        return await res.json();
    } catch (e) {
        return null;
    }
}

export async function deleteSession(id: string): Promise<boolean> {
    try {
        const res = await fetch(`${getBase()}/sessions/${id}`, { method: "DELETE" });
        return res.ok;
    } catch (e) {
        return false;
    }
}

export async function getConfig(): Promise<any> {
    try {
        const res = await fetch(`${getBase()}/config`);
        return await res.json();
    } catch (e) { return null; }
}

export async function updateConfig(data: any): Promise<any> {
    try {
        const res = await fetch(`${getBase()}/config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
        return await res.json();
    } catch (e) { return null; }
}

export async function getSystemStatus(): Promise<any> {
    try {
        console.log("[API] Fetching system status...");
        const res = await fetch(`${getBase()}/status`);
        if (!res.ok) {
            console.error("[API] Status check failed:", res.status, res.statusText);
            return null;
        }
        const data = await res.json();
        console.log("[API] Status received:", data);
        return data;
    } catch (e) {
        console.error("[API] Status check exception:", e);
        return null;
    }
}

export async function startMCPServers(servers: string[] = ["docker", "k8s_local", "k8s_remote"]): Promise<boolean> {
    try {
        const res = await fetch(`${getBase()}/mcp/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ servers })
        });
        return res.ok;
    } catch (e) { return false; }
}

export async function stopMCPServers(servers: string[]): Promise<boolean> {
    try {
        const res = await fetch(`${getBase()}/mcp/stop`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ servers })
        });
        return res.ok;
    } catch (e) { return false; }
}

export async function scanModels(host: string): Promise<string[]> {
    try {
        const res = await fetch(`${getBase()}/models/scan`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ host })
        });
        if (!res.ok) return [];
        const data = await res.json();
        return data.models || [];
    } catch (e) { return []; }
}

export async function confirmAction(tool: string, args: any, session_id?: string): Promise<any> {
    try {
        const res = await fetch(`${getBase()}/chat/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tool, arguments: args, session_id })
        });
        return await res.json();
    } catch (e) { return { error: String(e) }; }
}

export async function getPulseStatus(): Promise<any> {
    try {
        const res = await fetch(`${getBase()}/pulse/status`);
        if (!res.ok) return null;
        return await res.json();
    } catch (e) { return null; }
}

export async function getPulseIndex(): Promise<any> {
    try {
        const res = await fetch(`${getBase()}/pulse/index`);
        if (!res.ok) return null;
        return await res.json();
    } catch (e) { return null; }
}
