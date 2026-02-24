import { parse } from "@babel/parser";
import traverseModule from "@babel/traverse";
const traverse = traverseModule.default;
import generateModule from "@babel/generator";
const generate = generateModule.default;

import * as t from "@babel/types";
import prettier from "prettier";
import { v4 as uuidv4 } from "uuid";

export async function mutate(code, mutation) {
  const ast = parse(code, {
    sourceType: "module",
    plugins: ["typescript", "jsx"]
  });

  // Lazy instrumentation: ensure node ids exist
  instrumentNodeIds(ast);

  if (mutation.type === "update_classname") {
    applyClassnameMutation(ast, mutation);
  }

  const output = generate(ast, { retainLines: false }).code;

  const formatted = await prettier.format(output, {
    parser: "typescript"
  });

  return formatted;
}

/* ------------------------------------------ */
/* Lazy Instrumentation */
/* ------------------------------------------ */

function instrumentNodeIds(ast) {
  traverse(ast, {
    JSXOpeningElement(path) {
      const hasId = path.node.attributes.some(
        attr =>
          t.isJSXAttribute(attr) &&
          attr.name.name === "data-node-id"
      );

      if (!hasId) {
        path.node.attributes.push(
          t.jsxAttribute(
            t.jsxIdentifier("data-node-id"),
            t.stringLiteral("node_" + uuidv4())
          )
        );
      }
    }
  });
}

/* ------------------------------------------ */
/* Classname Mutation */
/* ------------------------------------------ */

function applyClassnameMutation(ast, mutation) {
  const { nodeId, add = [], remove = [] } = mutation;

  traverse(ast, {
    JSXOpeningElement(path) {
      const nodeIdAttr = path.node.attributes.find(
        attr =>
          t.isJSXAttribute(attr) &&
          attr.name.name === "data-node-id" &&
          attr.value &&
          attr.value.value === nodeId
      );

      if (!nodeIdAttr) return;

      let classAttr = path.node.attributes.find(
        attr =>
          t.isJSXAttribute(attr) &&
          attr.name.name === "className"
      );

      if (!classAttr) {
        classAttr = t.jsxAttribute(
          t.jsxIdentifier("className"),
          t.stringLiteral("")
        );
        path.node.attributes.push(classAttr);
      }

      const currentClasses = classAttr.value.value
        ? classAttr.value.value.split(/\s+/).filter(Boolean)
        : [];

      let updatedClasses = [...currentClasses];

      // 1️⃣ Explicit removals
      updatedClasses = updatedClasses.filter(c => !remove.includes(c));

      // 2️⃣ Conflict removal based on Tailwind groups
      for (const newClass of add) {
        updatedClasses = updatedClasses.filter(
          existing => !isConflicting(existing, newClass)
        );
      }

      // 3️⃣ Add new classes safely
      for (const newClass of add) {
        if (!updatedClasses.includes(newClass)) {
          updatedClasses.push(newClass);
        }
      }

      classAttr.value = t.stringLiteral(updatedClasses.join(" "));
    }
  });
}
function isConflicting(existing, incoming) {
  const groups = [
    // Text Size
    {
      name: "text-size",
      pattern: /^text-(xs|sm|base|lg|xl|\d?xl)$/
    },

    // Text Color
    {
      name: "text-color",
      pattern: /^text-(?!xs|sm|base|lg|xl|\d?xl)[a-z]+-\d{3}$/
    },

    // Background Color
    {
    name: "background",
    pattern: /^(bg-|from-|via-|to-)/
    },

    // Padding
    {
      name: "padding",
      pattern: /^p[trblxy]?-\d+$/
    },

    // Margin
    {
      name: "margin",
      pattern: /^m[trblxy]?-\d+$/
    },

    // Border Radius
    {
      name: "rounded",
      pattern: /^rounded(-[a-z]+)?$/
    },

    // Border Width
    {
      name: "border-width",
      pattern: /^border(-\d+)?$/
    },

    // Width
    {
      name: "width",
      pattern: /^w-\d+\/?\d*$/
    },

    // Height
    {
      name: "height",
      pattern: /^h-\d+\/?\d*$/
    }
  ];

  let existingGroup = null;
  let incomingGroup = null;

  for (const group of groups) {
    if (group.pattern.test(existing)) {
      existingGroup = group.name;
    }
    if (group.pattern.test(incoming)) {
      incomingGroup = group.name;
    }
  }

  return existingGroup && incomingGroup && existingGroup === incomingGroup;
}
