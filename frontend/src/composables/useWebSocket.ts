/**
 * WebSocket 组合式函数
 * 提供与后端 WebSocket 的连接管理、消息收发和自动清理功能
 */
import { ref, onUnmounted } from 'vue';
import { useAgentStore } from '../stores/agentStore.ts';
import type { RealtimeMessage } from '../types/agent.ts';

/** WebSocket 连接实例 */
let wsInstance: WebSocket | null = null;

/** 重连计数器 */
let reconnectCount = 0;

/** 最大重连次数 */
const MAX_RECONNECT = 5;

/** 重连延迟基数（毫秒） */
const RECONNECT_BASE_DELAY = 1000;

/** 重连定时器 */
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function useWebSocket() {
  const isConnected = ref<boolean>(false);
  const error = ref<string | null>(null);
  const agentStore = useAgentStore();

  /**
   * 建立 WebSocket 连接
   * @param taskId - 分析任务 ID，用于构建 WebSocket 路径
   */
  function connect(taskId: string): void {
    disconnect();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/${taskId}`;

    try {
      wsInstance = new WebSocket(url);

      wsInstance.onopen = () => {
        isConnected.value = true;
        error.value = null;
        reconnectCount = 0;
      };

      wsInstance.onmessage = (event: MessageEvent) => {
        try {
          const message: RealtimeMessage = JSON.parse(event.data as string);
          agentStore.handleRealtimeMessage(message);
        } catch (parseError) {
          console.error('[WebSocket] 消息解析失败:', parseError);
        }
      };

      wsInstance.onclose = (event: CloseEvent) => {
        isConnected.value = false;

        if (!event.wasClean && reconnectCount < MAX_RECONNECT) {
          const delay = RECONNECT_BASE_DELAY * Math.pow(2, reconnectCount);
          reconnectCount++;
          reconnectTimer = setTimeout(() => {
            connect(taskId);
          }, delay);
        }
      };

      wsInstance.onerror = () => {
        error.value = 'WebSocket 连接失败';
        isConnected.value = false;
      };
    } catch (connectError) {
      error.value = `WebSocket 连接异常: ${connectError}`;
    }
  }

  /**
   * 断开 WebSocket 连接
   * 清理重连定时器并关闭连接
   */
  function disconnect(): void {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    reconnectCount = MAX_RECONNECT;

    if (wsInstance !== null) {
      wsInstance.onclose = null;
      wsInstance.onerror = null;
      wsInstance.onmessage = null;
      wsInstance.onopen = null;

      if (wsInstance.readyState === WebSocket.OPEN || wsInstance.readyState === WebSocket.CONNECTING) {
        wsInstance.close(1000, '客户端主动断开');
      }
      wsInstance = null;
    }

    isConnected.value = false;
    error.value = null;
  }

  /**
   * 发送消息到 WebSocket 服务端
   * @param data - 要发送的数据，会被序列化为 JSON
   * @returns 是否发送成功
   */
  function send(data: unknown): boolean {
    if (wsInstance === null || wsInstance.readyState !== WebSocket.OPEN) {
      console.warn('[WebSocket] 连接未就绪，无法发送消息');
      return false;
    }

    try {
      wsInstance.send(JSON.stringify(data));
      return true;
    } catch (sendError) {
      console.error('[WebSocket] 消息发送失败:', sendError);
      return false;
    }
  }

  onUnmounted(() => {
    disconnect();
  });

  return {
    isConnected,
    error,
    connect,
    disconnect,
    send,
  };
}
