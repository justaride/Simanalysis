#!/usr/bin/env node
// Generates ../packages/s4tk_minimal_buff_tuning.package from the XML fixture.
// Requires @s4tk/models 0.6.14 and @s4tk/compression on Node's module path.

const fs = require("fs");
const path = require("path");
const { Package, XmlResource } = require("@s4tk/models");
const { CompressionType } = require("@s4tk/compression");

const fixtureDir = path.resolve(__dirname, "..");
const xmlPath = path.join(__dirname, "s4tk_minimal_buff_tuning.xml");
const packagePath = path.join(
  fixtureDir,
  "packages",
  "s4tk_minimal_buff_tuning.package",
);

const xml = fs.readFileSync(xmlPath, "utf8").trim();
const resource = new XmlResource(xml, {
  defaultCompressionType: CompressionType.ZLIB,
});
const packageFile = new Package([
  {
    key: {
      type: 0x6017e896,
      group: 0,
      instance: 98765n,
    },
    value: resource,
  },
]);

fs.mkdirSync(path.dirname(packagePath), { recursive: true });
fs.writeFileSync(packagePath, packageFile.getBuffer(false, false));
console.log(packagePath);
