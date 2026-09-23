#include "CoSave.h"
#include "Game.h"
#include "Papyrus.h"
#include "Sinks.h"

namespace
{
	// After F4SE::Init: log_directory() is built from the save folder name, which Init fills in.
	// The previous run's log is kept as Silhouette.prev.log -- the run that follows a crash is the
	// run that would otherwise erase the only record of it (Rapport's scar).
	void InitLogging()
	{
		auto path = logger::log_directory();
		if (!path) {
			return;
		}
		*path /= SH_PROJECT_NAME ".log"sv;

		std::error_code ec;
		auto            previous = *path;
		previous.replace_extension(".prev.log");
		std::filesystem::remove(previous, ec);
		std::filesystem::rename(*path, previous, ec);

		auto sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(path->string(), true);
		auto log = std::make_shared<spdlog::logger>("global log"s, std::move(sink));
		log->set_level(spdlog::level::info);
		log->flush_on(spdlog::level::info);
		spdlog::set_default_logger(std::move(log));
		spdlog::set_pattern("[%H:%M:%S.%e] [%l] %v"s);
	}

	void MessageHandler(F4SE::MessagingInterface::Message* a_message)
	{
		if (!a_message) {
			return;
		}
		switch (a_message->type) {
		case F4SE::MessagingInterface::kGameDataReady:
			SH::Game::Load();
			SH::Sinks::Attach();
			break;
		case F4SE::MessagingInterface::kPreLoadGame:
			// Everything queued belongs to the save being left. FF-prefixed ids are allocated per
			// save: the same number over there is somebody else.
			SH::Game::ForgetInbox();
			SH::Game::TheDirector().ForgetWorld();
			break;
		case F4SE::MessagingInterface::kNewGame:
			// A new game from the main menu sends no kPreLoadGame.
			SH::Game::ForgetInbox();
			SH::Game::TheDirector().ForgetWorld();
			SH::Sinks::Attach();
			break;
		case F4SE::MessagingInterface::kPostLoadGame:
			SH::Sinks::Attach();
			logger::info("after loading: {} record(s); {}", SH::Game::TheDirector().RecordCount(), SH::Sinks::Status());
			break;
		default:
			break;
		}
	}
}

extern "C" DLLEXPORT bool F4SEAPI F4SEPlugin_Query(const F4SE::QueryInterface* a_f4se, F4SE::PluginInfo* a_info)
{
	a_info->infoVersion = F4SE::PluginInfo::kVersion;
	a_info->name = SH_PROJECT_NAME;
	a_info->version = SH_VERSION_MAJOR * 10000 + SH_VERSION_MINOR * 100 + SH_VERSION_PATCH;

	if (a_f4se->IsEditor()) {
		return false;
	}
	// Every address this plugin resolves is an OG 1.10.163 id (S-18). Refusing another runtime is
	// the honest failure; resolving ids that mean something else there is not.
	return a_f4se->RuntimeVersion() == F4SE::RUNTIME_1_10_163;
}

extern "C" DLLEXPORT bool F4SEAPI F4SEPlugin_Load(const F4SE::LoadInterface* a_f4se)
{
	// false: F4SE's own logger would name the file after an empty plugin name (".log").
	F4SE::Init(a_f4se, false);
	InitLogging();
	logger::info("{} v{}", SH_PROJECT_NAME, SH_VERSION_STRING);

	const auto papyrus = F4SE::GetPapyrusInterface();
	if (!papyrus || !papyrus->Register(SH::Papyrus::Register)) {
		logger::critical("could not register the papyrus functions");
		return false;
	}
	if (!SH::CoSave::Register(F4SE::GetSerializationInterface())) {
		logger::error("no co-save: nothing Silhouette decides will be remembered between saves");
	}
	const auto messaging = F4SE::GetMessagingInterface();
	if (!messaging || !messaging->RegisterListener(MessageHandler)) {
		logger::critical("could not register the messaging listener");
		return false;
	}
	logger::info("loaded");
	return true;
}
