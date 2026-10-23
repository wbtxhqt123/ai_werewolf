from __future__ import annotations
import os
import json
from typing import TYPE_CHECKING, Any, List

from llm_player.controller import LLMClient, MockLLMClient

if TYPE_CHECKING:
    from game.game import Game
    from game.player import Player


ROLE_ZH_MAP = {
    "Villager": "村民",
    "Werewolf": "狼人",
    "Witch": "女巫",
    "Seer": "预言家",
    "Guard": "守卫",
    "Hunter": "猎人",
    "Black Werewolf King": "黑狼王",
    "Unknown": "未知",
}

PERSONALITY_ZH_MAP = {
    "cautious": "谨慎分析",
    "aggressive": "激进强势",
    "analytical": "逻辑推理",
    "emotional": "感性直觉",
    "diplomat": "温和斡旋",
    "follower": "顺势跟票",
    "manipulative": "话术博弈",
    "paranoid": "多疑敏感",
    "silent": "冷静寡言",
    "random": "跳脱奇招",
}


class GameEvaluator:
    """Evaluates player performance and handles multi-turn follow-up chat."""

    def __init__(
        self,
        api_key: str | None = None,
        language: str = "zh",
        base_url: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        llm_client: Any | None = None,
    ):
        self.has_api_key = bool(api_key or llm_client)
        self.llm_client = llm_client or (
            LLMClient(
                api_key=api_key,
                base_url=base_url,
                model=model,
                provider=provider,
            )
            if api_key
            else None
        )
        self.language = language
        self.prompt_dir = os.path.join(os.path.dirname(__file__), "prompts")
        self.current_mode = None
        self.game_summary = ""
        self.player_role = ""
        self.game_result = ""
        self.previous_evaluation = ""
        self.chat_history: list[dict[str, str]] = []

    def _load_prompt(self, prompt_type: str, name: str) -> str:
        """Loads a prompt template from a file."""
        path_parts = [self.prompt_dir, self.language, prompt_type, f"{name}.txt"]
        file_path = os.path.join(*path_parts)
        
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # Fallback to English if specific language file not found
            if self.language != "en":
                path_parts[1] = "en"
                file_path = os.path.join(*path_parts)
                with open(file_path, "r", encoding='utf-8') as f:
                    return f.read()
            raise

    def _generate_game_summary(self, game_logs: List[dict], player_name: str) -> str:
        """Summarizes the game logs into a concise text."""
        summary = []
        for log in game_logs:
            msg = log.get('message', '')
            if isinstance(msg, dict):
                msg = msg.get(self.language, msg.get('en', str(msg)))
            summary.append(f"- {msg}")
        return "\n".join(summary)

    def _call_llm_text(self, prompt: str) -> str:
        if not self.llm_client:
            return ""
        try:
            return self.llm_client.get_completion(prompt, json_mode=False)
        except TypeError:
            return self.llm_client.get_completion(prompt)

    def _build_local_fallback_evaluation(self, mode: str) -> str:
        is_zh = self.language == "zh"
        if is_zh:
            if mode == "mean":
                return (
                    f"**【😈 毒舌复盘】**\n"
                    f"- **你的身份**：{self.player_role}（{self.game_result}）\n"
                    f"- 这一局场上局势瞬息万变，你在发言和站边节奏上还有不少可以抠细节的地方！"
                    f"想替自己辩解或者问我哪一轮投错了？直接在下方发消息跟我对线！"
                )
            elif mode == "neutral":
                return (
                    f"**【😐 客观复盘】**\n"
                    f"- **你的身份**：{self.player_role}（{self.game_result}）\n"
                    f"- 本局已按屠边规则结算。综合全场时间线来看，夜间技能博弈与白天的归票方向决定了最终胜负。"
                    f"你可以继续向我提问任何轮次的细节！"
                )
            else:
                return (
                    f"**【😊 温和鼓励】**\n"
                    f"- **你的身份**：{self.player_role}（{self.game_result}）\n"
                    f"- 辛苦啦！不管胜负如何，你在本局中的参与和推理都很有亮点。有什么想复盘的细节随时问我吧！"
                )
        else:
            if mode == "mean":
                return (
                    f"**[😈 Sneer Review]**\n"
                    f"- **Your Role**: {self.player_role} ({self.game_result})\n"
                    f"- Quite a wild match! There were definitely some questionable votes and reads out there. "
                    f"Think you played it right? Reply below and defend your moves!"
                )
            elif mode == "neutral":
                return (
                    f"**[😐 Objective Review]**\n"
                    f"- **Your Role**: {self.player_role} ({self.game_result})\n"
                    f"- The match concluded under Slaughter-the-Side rules. Night actions and daytime vote alignment decided the outcome. "
                    f"Ask me about any specific turn below!"
                )
            else:
                return (
                    f"**[😊 Supportive Coach]**\n"
                    f"- **Your Role**: {self.player_role} ({self.game_result})\n"
                    f"- Good game! You stayed engaged through the twists and turns. Feel free to ask me anything about the match!"
                )

    def evaluate(self, game_logs: List[dict], player_name: str, player_role: str, game_result: str, mode: str) -> str:
        """Generates an evaluation of the player's performance."""
        self.current_mode = mode
        self.game_summary = self._generate_game_summary(game_logs, player_name)
        result_zh_map = {
            "Game Over": "游戏结束",
            "Winner: Villagers": "获胜阵营：好人阵营（村民）",
            "Winner: Werewolves": "获胜阵营：狼人阵营",
        }
        if self.language == "zh":
            self.player_role = ROLE_ZH_MAP.get(player_role, player_role)
            self.game_result = result_zh_map.get(game_result, game_result)
        else:
            self.player_role = player_role
            self.game_result = game_result

        if not self.llm_client:
            self.previous_evaluation = self._build_local_fallback_evaluation(mode)
            self.chat_history = [{"role": "assistant", "content": self.previous_evaluation}]
            return self.previous_evaluation

        prompt_template = self._load_prompt("evaluation", mode)
        prompt = prompt_template.format(
            game_summary=self.game_summary,
            player_role=self.player_role,
            game_result=self.game_result
        )

        raw = self._call_llm_text(prompt)
        # If LLM client returned a fallback JSON error string because of network/API error, use clean fallback
        if raw and raw.strip().startswith('{"thought": "Error calling LLM'):
            self.previous_evaluation = self._build_local_fallback_evaluation(mode)
        else:
            self.previous_evaluation = raw or self._build_local_fallback_evaluation(mode)

        self.chat_history = [{"role": "assistant", "content": self.previous_evaluation}]
        return self.previous_evaluation

    def chat(self, user_message: str) -> str:
        """Responds to the user's message in the context of the evaluation with multi-turn memory."""
        if not self.previous_evaluation:
            return "Error: No evaluation context found."

        self.chat_history.append({"role": "user", "content": user_message})

        if not self.llm_client:
            is_zh = self.language == "zh"
            reply = (
                f"从本局记录来看（你的身份是{self.player_role}，{self.game_result}），你提到的「{user_message}」确实是胜负手之一！"
                f"如果你想直接质问场上的 AI 玩家为什么那么操作，可以切换到旁边的 **🗣️ 揪人复盘互辩** 标签页把他们拉出来当面对线！"
                if is_zh
                else f"Looking at the match record (Role: {self.player_role}, {self.game_result}), your point about '{user_message}' was a key turning point! "
                     f"You can also switch to the **🗣️ Argue with AIs** tab to confront the AI players directly!"
            )
            self.chat_history.append({"role": "assistant", "content": reply})
            return reply

        mode_descriptions = {
            "mild": "You are supportive and constructive.",
            "neutral": "You are objective and analytical.",
            "mean": "You are harsh, sarcastic, and critical."
        }
        
        if self.language == "zh":
            mode_descriptions = {
                "mild": "你是支持和建设性的。",
                "neutral": "你是客观和分析性的。",
                "mean": "你是严厉、讽刺和挑剔的。"
            }

        # Format multi-turn conversation history so the evaluator remembers earlier exchanges
        history_lines = []
        for turn in self.chat_history[:-1]:
            speaker = ("AI 评价员" if turn["role"] == "assistant" else "玩家 (Player 1)") if self.language == "zh" else ("Evaluator" if turn["role"] == "assistant" else "Player 1")
            history_lines.append(f"{speaker}: {turn['content']}")
        conversation_context = "\n\n".join(history_lines)

        prompt_template = self._load_prompt("evaluation", "chat")
        prompt = prompt_template.format(
            mode=self.current_mode,
            mode_description=mode_descriptions.get(self.current_mode or "neutral", ""),
            game_summary=self.game_summary,
            player_role=self.player_role,
            game_result=self.game_result,
            previous_evaluation=conversation_context,
            user_message=user_message
        )

        reply = self._call_llm_text(prompt)
        if not reply or reply.strip().startswith('{"thought": "Error calling LLM'):
            reply = (
                "（AI 评价员暂时开小差了，请检查 API Key 或稍后重试。）"
                if self.language == "zh"
                else "(Evaluator could not reach the LLM API. Please check your API key or try again.)"
            )
        self.chat_history.append({"role": "assistant", "content": reply})
        return reply


class PostGameDebateRoom:
    """Manages post-game group arguments where the human player picks AI players to argue with."""

    def __init__(self, game: Game, default_llm_config: dict | None = None):
        self.game = game
        self.default_llm_config = default_llm_config or {}
        self.history: list[dict[str, Any]] = []

    def _get_player_personality(self, player: Player) -> str:
        ctrl = getattr(player, "controller", None)
        p = getattr(ctrl, "personality", None)
        if p:
            return str(p)
        personalities = ["cautious", "aggressive", "analytical", "emotional", "diplomat", "follower", "manipulative", "paranoid", "silent"]
        try:
            idx = int(player.name.replace("Player ", "")) % len(personalities)
            return personalities[idx]
        except Exception:
            return "analytical"

    def _get_llm_client_for_player(self, player: Player, override_config: dict | None = None) -> LLMClient | None:
        ctrl = getattr(player, "controller", None)
        existing_client = getattr(ctrl, "llm_client", None)
        if isinstance(existing_client, LLMClient) and existing_client.api_key:
            return existing_client

        cfg = override_config or self.default_llm_config or {}
        api_key = cfg.get("api_key")
        if api_key:
            return LLMClient(
                api_key=api_key,
                base_url=cfg.get("base_url"),
                model=cfg.get("model_name") or cfg.get("model"),
                provider=cfg.get("provider"),
            )
        return None

    def _build_local_fallback_reply(self, player: Player, user_message: str, lang: str, recent_turn_replies: list[dict]) -> str:
        is_zh = lang == "zh"
        role_en = player.role.name if player.role else "Villager"
        role_zh = ROLE_ZH_MAP.get(role_en, role_en)
        winner = self.game.winner or "Unknown"
        is_wolf = role_en in ("Werewolf", "Black Werewolf King")
        my_camp_won = (is_wolf and winner == "Werewolves") or ((not is_wolf) and winner == "Villagers")

        # Gather this player's actual speeches and votes from the game
        my_votes = []
        for v in getattr(self.game, "vote_history", []):
            target = (v.get("votes") or {}).get(player.name)
            if target:
                my_votes.append(f"Day {v.get('day')} ({v.get('phase')}): {target}")

        other_speaker_ref = ""
        if recent_turn_replies:
            prev = recent_turn_replies[-1]
            other_speaker_ref = (
                f"至于刚发言的 {prev['player'].replace('Player ', '')}号，你的操作大家也都看在眼里！"
                if is_zh
                else f"And as for {prev['player']} who just spoke, we all saw your moves too! "
            )

        if is_zh:
            win_str = "反正最后我们阵营赢了，战果说明一切！" if my_camp_won else "虽然这把输了很可惜，但当时在我的视角里逻辑是闭环的！"
            vote_str = f"（本局我的投票记录：{', '.join(my_votes[:3])}）" if my_votes else ""
            if is_wolf:
                return f"我是 **{role_zh}**！在场上我当然要伪装身份带节奏、找神职和村民的破绽了。{other_speaker_ref}你问「{user_message}」？狼人阵营本来就是要误导好人站边，{win_str}{vote_str}"
            else:
                return f"我底牌是好人阵营的 **{role_zh}**！当时场上信息有限，我每一票和发言都是为了帮好人找狼。{other_speaker_ref}{win_str}{vote_str}"
        else:
            win_str = "Our camp won in the end, so the result speaks for itself!" if my_camp_won else "Even though we lost, my reads made sense from my perspective at the time!"
            if is_wolf:
                return f"I was a **{role_en}**! Of course I had to bluff and misdirect the table to hunt down your side. {other_speaker_ref}{win_str}"
            else:
                return f"My true role was **{role_en}**! With limited information during the day, I played to find the wolves. {other_speaker_ref}{win_str}"

    def argue(
        self,
        selected_players: list[str],
        user_message: str,
        language: str = "zh",
        override_llm_config: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Generates in-character post-game argument responses from the selected AI players."""
        is_zh = language == "zh"
        human_player = self.game.get_player_by_name("Player 1")
        human_role_en = human_player.role.name if (human_player and human_player.role) else "Unknown"
        human_role_disp = ROLE_ZH_MAP.get(human_role_en, human_role_en) if is_zh else human_role_en

        self.history.append({
            "speaker": "Player 1",
            "role": human_role_en,
            "text": user_message,
        })

        # Build revealed roles roster & concise match log summary
        roster_lines = []
        for p in self.game.players:
            r_en = p.role.name if p.role else "Unknown"
            r_disp = ROLE_ZH_MAP.get(r_en, r_en) if is_zh else r_en
            status_disp = ("存活" if p.is_alive else "出局") if is_zh else ("Alive" if p.is_alive else "Eliminated")
            roster_lines.append(f"- {p.name}: {r_disp} ({status_disp})")
        roster_str = "\n".join(roster_lines)

        public_logs = []
        for entry in self.game.game_log[-60:]:
            if entry.log_type.name in ("PLAYER_THINKING", "PLAYER_DONE_THINKING"):
                continue
            if entry.log_type.name == "THOUGHT":
                continue
            public_logs.append(f"- [Day {entry.day}] {entry.get_text(language)}")
        log_summary_str = "\n".join(public_logs)

        winner_str = (
            ("好人阵营获胜" if self.game.winner == "Villagers" else "狼人阵营获胜")
            if is_zh
            else f"Winner: {self.game.winner}"
        )

        replies: list[dict[str, Any]] = []
        for p_name in selected_players:
            if p_name == "Player 1":
                continue
            player = self.game.get_player_by_name(p_name)
            if not player:
                continue

            role_en = player.role.name if player.role else "Unknown"
            role_disp = ROLE_ZH_MAP.get(role_en, role_en) if is_zh else role_en
            personality = self._get_player_personality(player)
            personality_disp = PERSONALITY_ZH_MAP.get(personality, personality) if is_zh else personality

            # Extract this AI player's private thoughts during the game
            my_thoughts = [
                f"- [Day {e.day}] {e.get_text(language)}"
                for e in self.game.game_log
                if e.log_type.name == "THOUGHT" and e.source == player
            ]
            thoughts_str = "\n".join(my_thoughts[-10:]) if my_thoughts else ("无" if is_zh else "None")

            # Format recent post-game debate history (including earlier AI replies in this same turn!)
            debate_lines = []
            for turn in self.history[-12:]:
                sp = turn["speaker"]
                sp_role = ROLE_ZH_MAP.get(turn.get("role", ""), turn.get("role", "")) if is_zh else turn.get("role", "")
                debate_lines.append(f"{sp} ({sp_role}): {turn['text']}")
            debate_transcript = "\n".join(debate_lines)

            llm_client = self._get_llm_client_for_player(player, override_llm_config)
            reply_text = ""

            if llm_client:
                if is_zh:
                    prompt = (
                        f"狼人杀对局已经结束（赛后复盘互辩阶段）！\n"
                        f"你是 **{player.name}**，你在本局的真实底牌是 **{role_disp}**，你的性格风格是 **{personality_disp}**。\n"
                        f"本局最终结果：{winner_str}。\n\n"
                        f"【全场玩家真实身份揭晓】\n{roster_str}\n\n"
                        f"【你在对局中的内心思考记录】\n{thoughts_str}\n\n"
                        f"【对局关键经过】\n{log_summary_str}\n\n"
                        f"【赛后复盘群聊记录】\n{debate_transcript}\n\n"
                        f"现在人类玩家（Player 1，真实身份：{human_role_disp}）点名拉你（以及被选中的其他 AI 玩家）一起赛后复盘辩论。\n"
                        f"请你以 **{player.name}（{role_disp}，性格：{personality_disp}）** 的第一人称口吻直接回复！\n"
                        f"要求：\n"
                        f"1. 结合你的真实身份、你在局内的实际操作/投票/发言，回应 Player 1 的质问或观点；如果前面已有其他 AI 玩家刚在复盘群聊里发言，你也可以顺带反驳、甩锅或声援他们！\n"
                        f"2. 语气要有真人在赛后复盘局的鲜活感（符合你的性格：{personality_disp}），控制在 2-4 句话，直接输出你的发言文本，不要输出 JSON。"
                    )
                else:
                    prompt = (
                        f"The Werewolf game has ended (Post-Game Debate Room)!\n"
                        f"You are **{player.name}**, your true role was **{role_disp}**, and your personality is **{personality_disp}**.\n"
                        f"Match Outcome: {winner_str}.\n\n"
                        f"[True Roles of All Players]\n{roster_str}\n\n"
                        f"[Your Private In-Game Thoughts]\n{thoughts_str}\n\n"
                        f"[Match Log Highlights]\n{log_summary_str}\n\n"
                        f"[Post-Game Debate Transcript]\n{debate_transcript}\n\n"
                        f"Human Player 1 (True Role: {human_role_disp}) picked you (and possibly other AI players) to argue/debrief after the match.\n"
                        f"Reply directly in first person as **{player.name} ({role_disp}, {personality_disp})**!\n"
                        f"Requirements:\n"
                        f"1. Defend or explain your actual in-game moves/votes/bluffs, respond directly to Player 1, and feel free to call out or banter with other AI players who just spoke in the debate transcript.\n"
                        f"2. Stay in character ({personality_disp}), keep it lively and concise (2-4 sentences), and output plain text only (NOT JSON)."
                    )
                try:
                    raw = llm_client.get_completion(prompt, json_mode=False)
                except TypeError:
                    raw = llm_client.get_completion(prompt)
                if raw and not raw.strip().startswith('{"thought": "Error calling LLM'):
                    reply_text = raw.strip()

            if not reply_text:
                reply_text = self._build_local_fallback_reply(player, user_message, language, replies)

            self.history.append({
                "speaker": player.name,
                "role": role_en,
                "text": reply_text,
            })
            replies.append({
                "player": player.name,
                "role": role_en,
                "personality": personality,
                "is_alive": player.is_alive,
                "reply": reply_text,
            })

        return replies
