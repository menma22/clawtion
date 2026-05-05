import { create } from 'zustand'

interface QueueStore {
  pollingInterval: number
  autoPoll: boolean
  setPollingInterval: (ms: number) => void
  setAutoPoll: (v: boolean) => void
}

export const useQueueStore = create<QueueStore>((set) => ({
  pollingInterval: 10_000,
  autoPoll: true,
  setPollingInterval: (pollingInterval) => set({ pollingInterval }),
  setAutoPoll: (autoPoll) => set({ autoPoll }),
}))
