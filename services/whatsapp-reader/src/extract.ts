/** Plain text of a WhatsApp message, or null for things worth no space (reactions, protocol and key-distribution messages). */
export function extractText(message: Record<string, any> | null | undefined): { text: string; kind: string } | null {
  if (!message) return null;
  const m = message.ephemeralMessage?.message ?? message.viewOnceMessage?.message ?? message.documentWithCaptionMessage?.message ?? message;
  if (m.conversation) return { text: String(m.conversation), kind: 'text' };
  if (m.extendedTextMessage?.text) return { text: String(m.extendedTextMessage.text), kind: 'text' };
  if (m.imageMessage) return { text: m.imageMessage.caption ? String(m.imageMessage.caption) : '[image]', kind: 'image' };
  if (m.videoMessage) return { text: m.videoMessage.caption ? String(m.videoMessage.caption) : '[video]', kind: 'video' };
  if (m.documentMessage) {
    const name = m.documentMessage.fileName ? String(m.documentMessage.fileName) : 'document';
    return { text: `[document: ${name}]${m.documentMessage.caption ? ' ' + m.documentMessage.caption : ''}`, kind: 'document' };
  }
  if (m.audioMessage) return { text: '[voice message]', kind: 'audio' };
  if (m.pollCreationMessage) return { text: `[poll] ${m.pollCreationMessage.name ?? ''}`.trim(), kind: 'poll' };
  if (m.locationMessage) return { text: '[location]', kind: 'location' };
  return null;
}
