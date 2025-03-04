// watest.cpp : This file contains the 'main' function. Program execution begins
// and ends there.
//
#include "pch.h"

#include <string>  // for string

#include "cfg.h"
#include "on_start.h"  // for OnStart, AppType, AppType::test
#include "providers/mrpe.h"
#include "system_error"  // for error_code
#include "test_tools.h"

namespace fs = std::filesystem;

/*
Typic output:

<<<mrpe>>>
(mode.com) Console 0 Status von Gert CON: 1 --------------------- 1
Codepage:        437 (chcp.com) sk 1 Geben Sie das Kennwort fuer "sk" ein:
*/

namespace cma::provider {  // to become friendly for wtools classes

class YamlLoaderMrpe {
public:
    YamlLoaderMrpe() {
        using namespace cma::cfg;
        std::error_code ec;
        std::filesystem::remove(cma::cfg::GetBakeryFile(), ec);
        cma::OnStart(cma::AppType::test);

        auto yaml = GetLoadedConfig();
        auto sections =
            GetInternalArray(groups::kGlobal, vars::kSectionsEnabled);
        sections.emplace_back(std::string(groups::kMrpe));
        PutInternalArray(groups::kGlobal, vars::kSectionsEnabled, sections);
        yaml[groups::kGlobal].remove(vars::kSectionsDisabled);
        yaml[groups::kGlobal][vars::kLogDebug] = "all";
        ProcessKnownConfigGroups();
        SetupEnvironmentFromGroups();
    }
    ~YamlLoaderMrpe() { OnStart(cma::AppType::test); }
};

TEST(SectionProviderMrpe, Construction) {
    YamlLoaderMrpe w;
    EXPECT_TRUE(cfg::groups::global.allowedSection(cfg::groups::kMrpe));
    MrpeProvider mrpe;
    EXPECT_EQ(mrpe.getUniqName(), cma::section::kMrpe);
    EXPECT_TRUE(mrpe.checks().empty());
    EXPECT_TRUE(mrpe.entries().empty());
    EXPECT_TRUE(mrpe.includes().empty());
    auto out = mrpe.generateContent();

    EXPECT_TRUE(out.empty());
}

void replaceYamlSeq(std::string_view group, std::string_view section,
                    const std::vector<std::string> &vec) {
    auto yaml = cfg::GetLoadedConfig();
    for (size_t i = 0; i < yaml[group][section].size(); i++)
        yaml[group][section].remove(0);

    yaml[group][section].reset();

    for (const auto &str : vec) {
        yaml[group][section].push_back(str);
    }
}

TEST(SectionProviderMrpe, SmallApi) {
    YamlLoaderMrpe w;
    std::string s = "a\rb\n\n";
    FixCrCnForMrpe(s);
    EXPECT_EQ(s, "a b\1\1");

    {
        auto [user, path] = cma::provider::ParseIncludeEntry(
            "sk = $CUSTOM_AGENT_PATH$\\mrpe_checks.cfg");
        EXPECT_EQ(user, "sk");
        EXPECT_EQ(path.u8string(), wtools::ToUtf8(cma::cfg::GetUserDir()) +
                                       "\\" + "mrpe_checks.cfg");
    }

    {
        auto [user, path] = cma::provider::ParseIncludeEntry(
            " = $CUSTOM_AGENT_PATH$\\mpe_cecks.cfg  ");
        EXPECT_TRUE(user.empty());
        EXPECT_EQ(path.u8string(), wtools::ToUtf8(cma::cfg::GetUserDir()) +
                                       "\\" + "mpe_cecks.cfg");
    }

    {
        auto [user, path] = cma::provider::ParseIncludeEntry(
            " = '$CUSTOM_AGENT_PATH$\\mpe_cecks.cfg'  ");
        EXPECT_TRUE(user.empty());
        EXPECT_EQ(path.u8string(), wtools::ToUtf8(cma::cfg::GetUserDir()) +
                                       "\\" + "mpe_cecks.cfg");
    }
}

TEST(SectionProviderMrpe, ConfigLoad) {
    XLOG::l(
        "The agent controller is not compatible with this Windows version. "
        "You can disable using the agent controller by configuring the "
        "Checkmk rule set \"Windows agent controller\" for this host.");
    auto test_fs_ = tst::TempCfgFs::Create();
    ASSERT_TRUE(test_fs_->loadFactoryConfig());
    tst::CreateWorkFile(
        std::filesystem::path{cfg::GetUserDir()} / "mrpe_checks.cfg",
        R"(check = Type 'c:\windows\system32\chcp.com')");
    MrpeProvider mrpe;
    EXPECT_EQ(mrpe.getUniqName(), cma::section::kMrpe);
    auto yaml = cfg::GetLoadedConfig();
    ASSERT_TRUE(yaml.IsMap());

    auto mrpe_yaml_optional = cfg::GetGroup(yaml, cfg::groups::kMrpe);
    ASSERT_TRUE(mrpe_yaml_optional.has_value());
    {
        auto &mrpe_cfg = mrpe_yaml_optional.value();

        ASSERT_TRUE(cfg::GetVal(mrpe_cfg, cfg::vars::kEnabled, false));
        auto entries =
            cfg::GetArray<std::string>(mrpe_cfg, cfg::vars::kMrpeConfig);
        EXPECT_EQ(entries.size(), 0)
            << "no mrpe expected";  // include and check
    }

    replaceYamlSeq(
        cfg::groups::kMrpe, cfg::vars::kMrpeConfig,
        {R"(check = Console 'c:\windows\system32\mode.com' CON CP /STATUS)",
         R"(include sk = $CUSTOM_AGENT_PATH$\mrpe_checks.cfg)",  // reference
         R"(Include=$CUSTOM_AGENT_PATH$\mrpe_checks.cfg)",       // no space
         R"(include  =   'mrpe_checks.cfg')",                    //
         R"(includes = $CUSTOM_AGENT_PATH$\mrpe_checks.cfg)",    // invalid
         R"(includ = $CUSTOM_AGENT_PATH$\mrpe_checks.cfg)",      // invalid
         R"(chck = Console 'c:\windows\system32\mode.com' CON CP /STATUS)",  // invalid
         R"(check = 'c:\windows\system32\mode.com' CON CP /STATUS)"});  // valid

    auto strings =
        cfg::GetArray<std::string>(cfg::groups::kMrpe, cfg::vars::kMrpeConfig);
    EXPECT_EQ(strings.size(), 8);
    mrpe.loadConfig();
    ASSERT_EQ(mrpe.includes().size(), 3);
    mrpe.loadConfig();
    ASSERT_EQ(mrpe.includes().size(), 3);
    EXPECT_EQ(mrpe.includes()[0],
              R"(sk = $CUSTOM_AGENT_PATH$\mrpe_checks.cfg)");
    EXPECT_EQ(mrpe.includes()[1], R"(=$CUSTOM_AGENT_PATH$\mrpe_checks.cfg)");
    EXPECT_EQ(mrpe.includes()[2], "=   'mrpe_checks.cfg'");
    ASSERT_EQ(mrpe.checks().size(), 2);
    EXPECT_EQ(mrpe.checks()[0],
              R"(Console 'c:\windows\system32\mode.com' CON CP /STATUS)");
    EXPECT_EQ(mrpe.checks()[1],
              R"('c:\windows\system32\mode.com' CON CP /STATUS)");

    EXPECT_EQ(mrpe.includes().size(), 3);
    EXPECT_EQ(mrpe.checks().size(), 2);
    constexpr size_t count = kMrpeRemoveAbsentFiles ? 4 : 5;
    EXPECT_EQ(mrpe.entries().size(), count);
}

TEST(SectionProviderMrpe, YmlCheck) {
    using namespace cma::cfg;
    tst::YamlLoader w;
    auto cfg = cma::cfg::GetLoadedConfig();

    auto mrpe_node = cfg[groups::kMrpe];
    ASSERT_TRUE(mrpe_node.IsDefined());
    ASSERT_TRUE(mrpe_node.IsMap());

    auto enabled = GetVal(groups::kMrpe, vars::kEnabled, false);
    EXPECT_TRUE(enabled);
    auto paths = GetArray<std::string>(groups::kMrpe, vars::kMrpeConfig);
    EXPECT_EQ(paths.size(), 0) << "base YAML must have 0 mrpe entries";
}

static auto CreateMrpeFiles(const fs::path &cfg_dir, const fs::path &file_dir) {
    auto mrpe_file_1 =
        tst::CreateWorkFile(file_dir / "mrpe1.bat", "@echo output_of_mrpe1");

    auto mrpe_file_2 =
        tst::CreateWorkFile(file_dir / "mrpe2.bat", "@echo output_of_mrpe2");

    std::string text = fmt::format(
        "# a\n"
        "  ;\n"  // expected clean
        "check = Type '{}'\n"
        "\n"
        "check = Type '{}'\n"
        "check = BadFile 'sss.bat'\n",
        mrpe_file_1.u8string(), mrpe_file_2.u8string());

    auto cfg_file = tst::CreateWorkFile(cfg_dir / "mrpe_check.cfg", text);
    return std::make_tuple(cfg_file, mrpe_file_1, mrpe_file_2);
}

TEST(SectionProviderMrpe, ProcessCfg) {
    tst::SafeCleanTempDir();
    auto [cfg_dir, file_dir] = tst::CreateInOut();
    ON_OUT_OF_SCOPE(tst::SafeCleanTempDir(););

    auto [cfg_file, mrpe_file_1, mrpe_file_2] =
        CreateMrpeFiles(cfg_dir, file_dir);

    std::vector<MrpeEntry> entries;

    AddCfgFileToEntries("", cfg_file, entries);
    ASSERT_EQ(entries.size(), 3);
    EXPECT_EQ(entries[0].command_line_, mrpe_file_1.u8string());
    EXPECT_EQ(entries[1].command_line_, mrpe_file_2.u8string());
    std::filesystem::path missing = cma::cfg::GetUserDir();
    missing /= "sss.bat";
    EXPECT_EQ(entries[2].command_line_, missing.u8string());
    auto result_1 = ExecMrpeEntry(entries[0], std::chrono::seconds(10));
    EXPECT_FALSE(result_1.empty());
    {
        auto table_1 = cma::tools::SplitString(result_1, " ");
        EXPECT_EQ(table_1.size(), 4);
        EXPECT_EQ(table_1[0], std::string("(") +
                                  wtools::ToStr(mrpe_file_1.filename()) + ")");
        EXPECT_EQ(table_1[1], "Type");
        EXPECT_EQ(table_1[2], "0");
        EXPECT_EQ(table_1[3], "output_of_mrpe1");
    }
    {
        auto result_2 = ExecMrpeEntry(entries[1], std::chrono::seconds(10));
        auto table_2 = cma::tools::SplitString(result_2, " ");
        EXPECT_FALSE(result_2.empty());
        EXPECT_EQ(table_2.size(), 4);
        EXPECT_EQ(table_2[0], std::string("(") +
                                  wtools::ToStr(mrpe_file_2.filename()) + ")");
        EXPECT_EQ(table_2[1], "Type");
        EXPECT_EQ(table_2[2], "0");
        EXPECT_EQ(table_2[3], "output_of_mrpe2");
    }
    auto result_missing = ExecMrpeEntry(entries[2], std::chrono::seconds(10));
    {
        EXPECT_FALSE(result_missing.empty());
        auto table_missing = cma::tools::SplitString(result_missing, " ", 3);
        EXPECT_EQ(table_missing.size(), 4);
        EXPECT_EQ(table_missing[0], "(sss.bat)");
        EXPECT_EQ(table_missing[1], "BadFile");
        EXPECT_EQ(table_missing[2], "3");
        EXPECT_EQ(table_missing[3],
                  "Unable to execute - plugin may be missing.");
    }
}

TEST(SectionProviderMrpe, Ctor) {
    {
        std::string base = "Codepage 'c:\\windows\\system32\\chcp.com' x d f";
        MrpeEntry me("", base);
        EXPECT_EQ(me.exe_name_, "chcp.com");
        EXPECT_EQ(me.full_path_name_, "c:\\windows\\system32\\chcp.com");
        EXPECT_EQ(me.command_line_, "c:\\windows\\system32\\chcp.com x d f");
        EXPECT_EQ(me.description_, "Codepage");
        ASSERT_FALSE(me.caching_.has_value());
    }

    {
        std::string base =
            "Codepage (123456:yes) 'c:\\windows\\system32\\chcp.com' x d f";
        MrpeEntry me("", base);
        EXPECT_EQ(me.exe_name_, "chcp.com");
        EXPECT_EQ(me.full_path_name_, "c:\\windows\\system32\\chcp.com");
        EXPECT_EQ(me.command_line_, "c:\\windows\\system32\\chcp.com x d f");
        EXPECT_EQ(me.description_, "Codepage");
        ASSERT_EQ(me.caching_->add_age, true);
        ASSERT_EQ(me.caching_->max_age, 123456);
    }
}

TEST(SectionProviderMrpe, Run) {
    YamlLoaderMrpe w;
    using namespace cma::cfg;
    MrpeProvider mrpe;
    EXPECT_EQ(mrpe.getUniqName(), cma::section::kMrpe);
    auto yaml = GetLoadedConfig();
    ASSERT_TRUE(yaml.IsMap());

    auto mrpe_yaml_optional = GetGroup(yaml, groups::kMrpe);
    ASSERT_TRUE(mrpe_yaml_optional.has_value());
    {
        auto &mrpe_cfg = mrpe_yaml_optional.value();

        ASSERT_TRUE(GetVal(mrpe_cfg, vars::kEnabled, false));
        auto entries = GetArray<std::string>(mrpe_cfg, vars::kMrpeConfig);
        ASSERT_EQ(entries.size(), 0)
            << "check that yml is ok";  // include and check
    }

    replaceYamlSeq(
        groups::kMrpe, vars::kMrpeConfig,
        {
            R"(check = Codepage 'c:\windows\system32\chcp.com')",
            R"(check = Console 'c:\windows\system32\mode.com' CON CP /STATUS)",
        });

    auto strings = GetArray<std::string>(groups::kMrpe, vars::kMrpeConfig);
    EXPECT_EQ(strings.size(), 2);
    mrpe.loadConfig();
    ASSERT_EQ(mrpe.includes().size(), 0);
    ASSERT_EQ(mrpe.checks().size(), 2);

    EXPECT_EQ(mrpe.entries().size(), 2);
    mrpe.updateSectionStatus();

    // sequential
    yaml[groups::kMrpe][vars::kMrpeParallel] = false;
    {
        auto accu = mrpe.generateContent();
        ASSERT_TRUE(!accu.empty());
        auto table = cma::tools::SplitString(accu, "\n");
        EXPECT_EQ(table[0], "<<<mrpe>>>");
        table.erase(table.begin());
        ASSERT_EQ(table.size(), 2);

        auto e0 = mrpe.entries()[0];
        {
            auto hdr = fmt::format("({})", e0.exe_name_) + " " +
                       e0.description_ + " 0";
            EXPECT_TRUE(table[0].find(hdr) == 0);
        }
        auto e1 = mrpe.entries()[1];
        {
            auto hdr = fmt::format("({})", e1.exe_name_) + " " +
                       e1.description_ + " 0";
            EXPECT_TRUE(table[1].find(hdr) == 0);
        }
    }

    yaml[groups::kMrpe][vars::kMrpeParallel] = true;
    {
        auto accu = mrpe.generateContent();
        ASSERT_TRUE(!accu.empty());
        auto table = cma::tools::SplitString(accu, "\n");
        table.erase(table.begin());
        ASSERT_EQ(table.size(), 2);

        auto e0 = mrpe.entries()[0];
        auto hdr0 =
            fmt::format("({})", e0.exe_name_) + " " + e0.description_ + " 0";

        auto e1 = mrpe.entries()[1];
        auto hdr1 =
            fmt::format("({})", e1.exe_name_) + " " + e1.description_ + " 0";
        { EXPECT_TRUE(table[0].find(hdr0) == 0 || table[1].find(hdr0) == 0); }
        { EXPECT_TRUE(table[0].find(hdr1) == 0 || table[1].find(hdr1) == 0); }
    }
}

TEST(SectionProviderMrpe, RunCachedIntegration) {
    YamlLoaderMrpe w;
    using namespace cma::cfg;
    MrpeProvider mrpe;
    EXPECT_EQ(mrpe.getUniqName(), cma::section::kMrpe);
    auto yaml = GetLoadedConfig();
    ASSERT_TRUE(yaml.IsMap());

    auto mrpe_yaml_optional = GetGroup(yaml, groups::kMrpe);
    ASSERT_TRUE(mrpe_yaml_optional.has_value());
    {
        auto &mrpe_cfg = mrpe_yaml_optional.value();

        ASSERT_TRUE(GetVal(mrpe_cfg, vars::kEnabled, false));
        auto entries = GetArray<std::string>(mrpe_cfg, vars::kMrpeConfig);
        ASSERT_EQ(entries.size(), 0)
            << "check that yml is ok";  // include and check
    }

    replaceYamlSeq(
        groups::kMrpe, vars::kMrpeConfig,
        {
            R"(check = Time 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' Get-Date -Format HHmmssffff)",
            R"(check = CachedTime (10:no) 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' Get-Date -Format HHmmssffff)",
            R"(check = CachedTimeWithAge (10:yes) 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' Get-Date -Format HHmmssffff)",
        });

    auto strings = GetArray<std::string>(groups::kMrpe, vars::kMrpeConfig);
    EXPECT_EQ(strings.size(), 3);
    mrpe.loadConfig();
    ASSERT_EQ(mrpe.includes().size(), 0);
    ASSERT_EQ(mrpe.checks().size(), 3);

    EXPECT_EQ(mrpe.entries().size(), 3);
    mrpe.updateSectionStatus();

    yaml[groups::kMrpe][vars::kMrpeParallel] = false;
    auto accu = mrpe.generateContent();
    ASSERT_TRUE(!accu.empty());
    auto table = cma::tools::SplitString(accu, "\n");
    EXPECT_EQ(table[0], "<<<mrpe>>>");

    // expect "(powershell.exe) Time 0 TIMESTAMP"
    auto result_1 = cma::tools::SplitString(table[1], " ");
    auto mrpe_1 = mrpe.entries()[0];
    EXPECT_EQ(result_1.size(), 4);
    EXPECT_EQ(result_1[0], fmt::format("({})", mrpe_1.exe_name_));
    EXPECT_EQ(result_1[1], mrpe_1.description_);
    EXPECT_EQ(result_1[2], "0");
    auto &time_1 = result_1[3];
    std::cout << time_1 << std::endl;

    // expect "(powershell.exe) CachedTime 0 TIMESTAMP"
    auto result_2 = cma::tools::SplitString(table[2], " ");
    auto mrpe_2 = mrpe.entries()[1];
    EXPECT_EQ(result_2.size(), 4);
    EXPECT_EQ(result_2[0], fmt::format("({})", mrpe_2.exe_name_));
    EXPECT_EQ(result_2[1], mrpe_2.description_);
    EXPECT_EQ(result_2[2], "0");
    auto &time_2 = result_2[3];

    // expect "(powershell.exe) CachedTimeWithAge 0 TIMESTAMP (DIFF;10)"
    auto result_3 = cma::tools::SplitString(table[3], " ");
    auto mrpe_3 = mrpe.entries()[2];
    EXPECT_EQ(result_3.size(), 5);
    EXPECT_EQ(result_3[0], fmt::format("({})", mrpe_3.exe_name_));
    EXPECT_EQ(result_3[1], mrpe_3.description_);
    EXPECT_EQ(result_3[2], "0");
    auto &time_3 = result_3[3];
    EXPECT_TRUE(result_3[3].find(";10)"));

    cma::tools::sleep(10);

    // expect TIMESTAMP to change for first check, while the other two are
    // cached and stay unchanged
    auto second_run = mrpe.generateContent();
    auto second_table = cma::tools::SplitString(second_run, "\n");
    EXPECT_TRUE(time_1 != cma::tools::SplitString(second_table[1], " ")[3]);
    EXPECT_TRUE(time_2 == cma::tools::SplitString(second_table[2], " ")[3]);
    EXPECT_TRUE(time_3 == cma::tools::SplitString(second_table[3], " ")[3]);
}

}  // namespace cma::provider
