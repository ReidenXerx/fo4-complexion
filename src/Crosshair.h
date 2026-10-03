#pragma once

// What the crosshair was on: the pick the sink saw last, and the ones it moved off, each with the time it
// left them. Plain 32-bit reference handles only: the sink runs on whatever thread the game sends the
// event from, so nothing is looked up there. Whoever asks -- the main thread -- looks each one up through
// a_wanted, outside the lock.

namespace CX
{
	class CrosshairTrail
	{
	public:
		// Enough for a look around a cluttered room: every door, chair and bottle the crosshair crosses
		// within reach is a pick of its own.
		static constexpr std::size_t kKept = 64;

		// The pick is now a_ref (0: nothing). The same pick again changes nothing: the view caster reports
		// every update, not only a change.
		void Note(std::uint32_t a_ref, std::int64_t a_nowMs)
		{
			std::scoped_lock l{ _lock };
			if (a_ref == _current) {
				return;
			}
			if (_current != 0) {
				_left[_next] = Left{ _current, a_nowMs };
				_next = (_next + 1) % kKept;
				_count = std::min(_count + 1, kKept);
			}
			_current = a_ref;
		}

		// A load: every handle belongs to the save being left.
		void Forget()
		{
			std::scoped_lock l{ _lock };
			_current = 0;
			_count = 0;
			_next = 0;
		}

		[[nodiscard]] std::uint32_t Current() const
		{
			std::scoped_lock l{ _lock };
			return _current;
		}

		// The pick now, if a_wanted takes it. Otherwise, when a_recentMs > 0, the newest pick the crosshair
		// left no more than a_recentMs ago that a_wanted takes: opening a menu takes the crosshair off them.
		// 0 if there is none.
		template <class Wanted>
		[[nodiscard]] std::uint32_t Choose(std::int64_t a_recentMs, std::int64_t a_nowMs, Wanted&& a_wanted) const
		{
			std::uint32_t                current = 0;
			std::array<Left, kKept>      newestFirst{};
			std::size_t                  count = 0;
			{
				std::scoped_lock l{ _lock };
				current = _current;
				count = _count;
				for (std::size_t i = 0; i < count; ++i) {
					newestFirst[i] = _left[(_next + kKept - 1 - i) % kKept];
				}
			}
			if (current != 0 && a_wanted(current)) {
				return current;
			}
			if (a_recentMs <= 0) {
				return 0;
			}
			for (std::size_t i = 0; i < count; ++i) {
				const auto& left = newestFirst[i];
				if (a_nowMs - left.ms > a_recentMs) {
					break;  // older still, from here on
				}
				if (a_wanted(left.ref)) {
					return left.ref;
				}
			}
			return 0;
		}

	private:
		struct Left
		{
			std::uint32_t ref{ 0 };
			std::int64_t  ms{ 0 };  // when the crosshair left it
		};

		mutable std::mutex      _lock;
		std::uint32_t           _current{ 0 };
		std::array<Left, kKept> _left{};
		std::size_t             _next{ 0 };
		std::size_t             _count{ 0 };
	};
}
